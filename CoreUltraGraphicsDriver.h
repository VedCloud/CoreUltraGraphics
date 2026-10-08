#ifndef CoreUltraGraphicsDriver_h
#define CoreUltraGraphicsDriver_h

#include <IOKit/IOService.h>
#include <IOKit/pci/IOPCIDevice.h>
#include <IOKit/IOMemoryMap.h>

class CoreUltraGraphicsDriver : public IOService
{
    OSDeclareDefaultStructors(CoreUltraGraphicsDriver);
private:
    IOPCIDevice *pciDevice;
    IOMemoryMap *mmioMap;
    volatile void *mmioBase;
    UInt32 mmioLength;
public:
    virtual bool init(OSDictionary *dict = nullptr) override;
    virtual void free() override;
    virtual IOService *probe(IOService *provider, SInt32 *score) override;
    virtual bool start(IOService *provider) override;
    virtual void stop(IOService *provider) override;
};

#endif
