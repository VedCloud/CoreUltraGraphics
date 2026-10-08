#ifndef CoreUltraGraphicsDriver_h
#define CoreUltraGraphicsDriver_h

#include <IOKit/IOService.h>
#include <IOKit/pci/IOPCIDevice.h>
#include <IOKit/IOBufferMemoryDescriptor.h>
#include <IOKit/graphics/IOFramebuffer.h>
#include <IOKit/graphics/IOGraphicsDevice.h>

class CoreUltraGraphicsDriver : public IOFramebuffer
{
    OSDeclareDefaultStructors(CoreUltraGraphicsDriver);

private:
    IOPCIDevice *pciDevice;
    IOMemoryMap *mmioMap;
    volatile void *mmioBase;
    UInt32 mmioLength;

    // Host-memory scratch buffer
    IOBufferMemoryDescriptor *scratchDesc;
    void *scratchVirt;
    IOPhysicalAddress scratchPhys;
    UInt32 scratchSize;

    // Framebuffer state
    IOMemoryDescriptor *fbMemory;
    IOMemoryMap *fbMap;
    void *fbVirt;
    IOPhysicalAddress fbPhys;
    UInt32 fbWidth;
    UInt32 fbHeight;
    UInt32 fbDepth;
    UInt32 fbPitch;
    UInt32 fbBytesPerRow;

    // Intel Meteor Lake register offsets (Gen12 display engine)
    static const uint32_t PWR_WELL_CTL1     = 0x45400;
    static const uint32_t HTOTAL_A          = 0x60000;
    static const uint32_t VTOTAL_A          = 0x6000C;
    static const uint32_t PIPE_SRC_A        = 0x6001C;
    static const uint32_t TRANS_DDI_FUNC_A  = 0x60400;
    static const uint32_t DDI_BUF_CTL_A     = 0x64000;
    static const uint32_t TRANSCONF_A       = 0x70008;
    static const uint32_t PLANE_CTL_1_A     = 0x70180;
    static const uint32_t PLANE_STRIDE_1_A  = 0x70188;
    static const uint32_t PLANE_SIZE_1_A    = 0x70190;
    static const uint32_t PLANE_SURF_1_A    = 0x7019C;
    static const uint32_t PLANE_CTL_EN      = (1u << 31);

    // Helper methods
    uint32_t readReg(uint32_t offset) const;
    void writeReg(uint32_t offset, uint32_t value);
    void logPciIdentity();
    void dumpDisplayState();
    void releaseScratchBuffer();
    void releaseResources();
    bool initDisplayEngine();
    bool initFramebuffer();

public:
    virtual bool init(OSDictionary *dict = nullptr) override;
    virtual void free() override;
    virtual IOService *probe(IOService *provider, SInt32 *score) override;
    virtual bool start(IOService *provider) override;
    virtual void stop(IOService *provider) override;

    // IOFramebuffer required methods
    virtual IODeviceMemory * getApertureRange(IOPixelAperture aperture) override;
    virtual const char * getPixelFormats( void ) override;
    virtual IOItemCount getDisplayModeCount( void ) override;
    virtual IOReturn getDisplayModes( IODisplayModeID * allDisplayModes ) override;
    virtual IOReturn getInformationForDisplayMode( IODisplayModeID displayMode, IODisplayModeInformation * info ) override;
    virtual UInt64 getPixelFormatsForDisplayMode( IODisplayModeID displayMode, IOOptionBits flags = 0 ) override;
    virtual IOReturn getPixelInformation( IOIndex *bytesPerRow, IOIndex *bytesPerPixel, IOIndex *bitsPerPixel, IOIndex *pixelsPerRow ) override;
    virtual IOReturn getCurrentDisplayMode( IODisplayModeID * displayMode, IOOptionBits flags = 0 ) override;
    virtual IOReturn setDisplayMode( IODisplayModeID displayMode, IOOptionBits flags = 0 ) override;

    // Optional
    virtual IOReturn flushDisplay(IOOptionBits options = 0) override;

    // Scratch buffer for command submission
    bool allocateHardwareScratchBuffer(uint32_t size);
};

#endif