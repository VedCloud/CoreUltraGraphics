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

    // Host-memory scratch buffer. NOTE: scratchPhys is a CPU physical address,
    // not a GPU-visible (GGTT/PPGTT) address.
    IOBufferMemoryDescriptor *scratchDesc;
    void *scratchVirt;
    IOPhysicalAddress scratchPhys;
    UInt32 scratchSize;

    uint32_t readReg(uint32_t offset) const;   // bounds-checked, read-only
    void logPciIdentity();
    void dumpDisplayState();                   // read-only diagnostics
    void releaseScratchBuffer();
    void releaseResources();

public:
    virtual bool init(OSDictionary *dict = nullptr) override;
    virtual void free() override;
    virtual IOService *probe(IOService *provider, SInt32 *score) override;
    virtual bool start(IOService *provider) override;
    virtual void stop(IOService *provider) override;

    bool allocateHardwareScratchBuffer(uint32_t size);
};

#endif