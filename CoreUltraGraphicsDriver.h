#ifndef CoreUltraGraphicsDriver_h
#define CoreUltraGraphicsDriver_h

#include <IOKit/IOService.h>
#include <IOKit/pci/IOPCIDevice.h>
#include <IOKit/IOBufferMemoryDescriptor.h>

class CoreUltraGraphicsDriver : public IOService
{
    OSDeclareDefaultStructors(CoreUltraGraphicsDriver);
private:
    IOPCIDevice *pciDevice;
    IOMemoryMap *mmioMap;
    volatile void *mmioBase;
    UInt32 mmioLength;

    IOBufferMemoryDescriptor *scratchDesc;
    IOMemoryMap *scratchMap;
    IOVirtualAddress scratchVirt;
    IOPhysicalAddress scratchPhys;
    UInt32 scratchSize;

public:
    virtual bool init(OSDictionary *dict = nullptr) override;
    virtual void free() override;
    virtual IOService *probe(IOService *provider, SInt32 *score) override;
    virtual bool start(IOService *provider) override;
    virtual void stop(IOService *provider) override;
    bool allocateHardwareScratchBuffer(uint32_t size);
};

#endif
