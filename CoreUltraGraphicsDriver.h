#ifndef CoreUltraGraphicsDriver_h
#define CoreUltraGraphicsDriver_h
#include <IOKit/IOService.h>
#include <IOKit/pci/IOPCIDevice.h>

// Metadata-only attachment milestone for the measured 8086:7D45 target.
class CoreUltraGraphicsDriver : public IOService
{
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
