#ifndef CoreUltraGraphicsDriver_h
#define CoreUltraGraphicsDriver_h
#include <IOKit/IOService.h>
#include <IOKit/pci/IOPCIDevice.h>

// One-shot read-only GMD identification milestone for measured 8086:7D45.
class CoreUltraGraphicsDriver : public IOService
{
    OSDeclareDefaultStructors(CoreUltraGraphicsDriver);
private:
    IOPCIDevice *pciDevice;
    void releaseResources();
    void readIdentification();
    void publishIdentification(const char *prefix, UInt32 raw);
public:
    bool init(OSDictionary *dict = nullptr) override;
    void free() override;
    IOService *probe(IOService *provider, SInt32 *score) override;
    bool start(IOService *provider) override;
    void stop(IOService *provider) override;
};
#endif
