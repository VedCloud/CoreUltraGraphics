// Diagnostic bridge for this Dell only. No register writes and no _BCM call
// during startup. A privileged, explicit test temporarily sets a firmware level.
#include <IOKit/IOService.h>
#include <IOKit/IOUserClient.h>
#include <IOKit/IOLocks.h>
#include <IOKit/pci/IOPCIDevice.h>
#include <IOKit/acpi/IOACPIPlatformDevice.h>
#include <libkern/c++/OSContainers.h>

class LatitudeBacklightProbe;
class LatitudeBacklightClient : public IOUserClient {
    OSDeclareDefaultStructors(LatitudeBacklightClient)
    LatitudeBacklightProbe *bridge {nullptr};
    bool changed {false};
    UInt32 original {0};
public:
    bool start(IOService *) override;
    IOReturn clientClose() override;
    IOReturn externalMethod(uint32_t, IOExternalMethodArguments *, IOExternalMethodDispatch * = nullptr,
                            OSObject * = nullptr, void * = nullptr) override;
};

class LatitudeBacklightProbe : public IOService {
    OSDeclareDefaultStructors(LatitudeBacklightProbe)
    IOPCIDevice *pci {nullptr};
    IOLock *lock {nullptr};
    IOACPIPlatformDevice *acpi() {
        return pci ? OSDynamicCast(IOACPIPlatformDevice,pci->getProperty("acpi-device")) : nullptr;
    }
    IOReturn current(IOACPIPlatformDevice *device, UInt32 *value) {
        return device->evaluateInteger("LCD._BQC",value);
    }
    bool allowed(IOACPIPlatformDevice *device, UInt32 value, UInt32 *low, UInt32 *high, UInt32 *count) {
        OSObject *object=nullptr;
        IOReturn result=device->evaluateObject("LCD._BCL",&object);
        OSArray *levels=OSDynamicCast(OSArray,object);
        bool match=false; *low=101; *high=0; *count=0;
        if(result==kIOReturnSuccess && levels && levels->getCount()>=3 && levels->getCount()<=256) {
            // First two _BCL values are AC/DC defaults, not selectable levels.
            for(unsigned i=2;i<levels->getCount();i++) {
                OSNumber *number=OSDynamicCast(OSNumber,levels->getObject(i));
                if(!number)continue;
                UInt64 native=number->unsigned64BitValue();
                if(native<5 || native>100)continue;
                UInt32 n=static_cast<UInt32>(native);
                if(n<*low)*low=n; if(n>*high)*high=n; ++*count;
                if(n==value)match=true;
            }
        }
        OSSafeReleaseNULL(object);
        return match;
    }
public:
    bool start(IOService *provider) override {
        pci=OSDynamicCast(IOPCIDevice,provider);
        if(!pci || pci->configRead16(0)!=0x8086 || pci->configRead16(2)!=0x7d45 ||
           pci->configRead16(0x2c)!=0x1028 || pci->configRead16(0x2e)!=0x0cb6)return false;
        if(!IOService::start(provider))return false;
        lock=IOLockAlloc(); if(!lock)return false;
        setProperty("DiagnosticOnly",true);
        setProperty("AutomaticBrightnessWrites",false);
        setProperty("FirmwarePath","_SB.PC00.GFX0.LCD");
        registerService(); return true;
    }
    void free() override {
        if(lock)IOLockFree(lock);
        IOService::free();
    }
    IOReturn newUserClient(task_t task,void *security,UInt32 type,OSDictionary *properties,IOUserClient **handler) override {
        *handler=nullptr;
        if(type!=0 || IOUserClient::clientHasPrivilege(security,kIOClientPrivilegeAdministrator)!=kIOReturnSuccess)
            return kIOReturnNotPrivileged;
        LatitudeBacklightClient *client=new LatitudeBacklightClient;
        if(!client)return kIOReturnNoMemory;
        if(!client->initWithTask(task,security,type,properties) || !client->attach(this) || !client->start(this)) {
            if(client->getProvider())client->detach(this);
            client->release(); return kIOReturnError;
        }
        *handler=client; return kIOReturnSuccess;
    }
    IOReturn status(UInt64 *out) {
        if(!lock)return kIOReturnNotReady;
        IOLockLock(lock);
        IOACPIPlatformDevice *device=acpi();
        if(!device){IOLockUnlock(lock);return kIOReturnNotFound;}
        UInt32 value=0,low=0,high=0,count=0;
        IOReturn bqc=current(device,&value);
        allowed(device,value,&low,&high,&count);
        out[0]=static_cast<UInt32>(device->validateObject("LCD._BCM"));
        out[1]=static_cast<UInt32>(bqc); out[2]=value;
        out[3]=low;out[4]=high;out[5]=count;
        setProperty("BQCStatus",static_cast<UInt32>(bqc),32);
        setProperty("FirmwareCurrentLevel",value,32);
        setProperty("FirmwareLevelCount",count,32);
        IOLockUnlock(lock);return kIOReturnSuccess;
    }
    IOReturn write(UInt32 requested,UInt32 *before) {
        if(!lock || requested<5 || requested>100)return kIOReturnBadArgument;
        IOLockLock(lock);
        IOACPIPlatformDevice *device=acpi();
        UInt32 value=0,low=0,high=0,count=0;
        if(!device || device->validateObject("LCD._BCM")!=kIOReturnSuccess ||
           current(device,&value)!=kIOReturnSuccess ||
           !allowed(device,value,&low,&high,&count) ||
           !allowed(device,requested,&low,&high,&count)) {
            IOLockUnlock(lock); return kIOReturnUnsupported;
        }
        OSNumber *number=OSNumber::withNumber(requested,32);
        if(!number){IOLockUnlock(lock);return kIOReturnNoMemory;}
        OSObject *params[]={number};
        IOReturn result=device->evaluateObject("LCD._BCM",nullptr,params,1);
        number->release();
        *before=value;
        setProperty("LastBCMStatus",static_cast<UInt32>(result),32);
        setProperty("LastRequestedLevel",requested,32);
        IOLockUnlock(lock);return result;
    }
};

OSDefineMetaClassAndStructors(LatitudeBacklightProbe,IOService)
OSDefineMetaClassAndStructors(LatitudeBacklightClient,IOUserClient)
bool LatitudeBacklightClient::start(IOService *provider) {
    bridge=OSDynamicCast(LatitudeBacklightProbe,provider);
    if(!bridge || !IOUserClient::start(provider) || !bridge->open(this))return false;
    return true;
}
IOReturn LatitudeBacklightClient::externalMethod(uint32_t selector,IOExternalMethodArguments *args,
    IOExternalMethodDispatch *,OSObject *,void *) {
    if(!bridge || !args)return kIOReturnNotReady;
    if(selector==0 && args->scalarInputCount==0 && args->scalarOutputCount==6 &&
       args->structureInputSize==0 && args->structureOutputSize==0)
        return bridge->status(args->scalarOutput);
    if(selector==1 && args->scalarInputCount==1 && args->scalarOutputCount==0 &&
       args->structureInputSize==0 && args->structureOutputSize==0 && args->scalarInput[0]<=100) {
        UInt32 before=0;
        IOReturn result=bridge->write(static_cast<UInt32>(args->scalarInput[0]),&before);
        if(result==kIOReturnSuccess && !changed){original=before;changed=true;}
        return result;
    }
    return kIOReturnBadArgument;
}
IOReturn LatitudeBacklightClient::clientClose() {
    if(bridge) {
        if(changed){UInt32 ignored=0;bridge->write(original,&ignored);changed=false;}
        if(bridge->isOpen(this))bridge->close(this);
    }
    terminate();return kIOReturnSuccess;
}
