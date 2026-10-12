#ifndef CORE_ULTRA_GRAPHICS_DRIVER_H
#define CORE_ULTRA_GRAPHICS_DRIVER_H
#include <IOKit/IOService.h>
#include <IOKit/pci/IOPCIDevice.h>

// Identification-only milestone. No MMIO, DMA or graphics provider.
class CoreUltraGraphicsDriver : public IOService {
    OSDeclareDefaultStructors(CoreUltraGraphicsDriver);
private:
    IOPCIDevice *pciDevice;
    void releaseResources();
public:
    bool init(OSDictionary *dict = nullptr) override;
    void free() override;
    IOService *probe(IOService *provider, SInt32 *score) override;
    bool start(IOService *provider) override;
    void stop(IOService *provider) override;
};
#endif
