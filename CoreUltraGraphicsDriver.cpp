#include "CoreUltraGraphicsDriver.h"

#define super IOFramebuffer
OSDefineMetaClassAndStructors(CoreUltraGraphicsDriver, IOFramebuffer);

// Display-engine registers. READ ONLY unless hwWritesEnabled.
// Offsets are Gen12-style (display-version-14); verify against Intel docs.
static const struct DumpReg { const char *name; uint32_t offset; } kDumpRegs[] = {
    { "PWR_WELL_CTL1",    0x45400 },
    { "HTOTAL_A",         0x60000 },
    { "VTOTAL_A",         0x6000C },
    { "PIPE_SRC_A",       0x6001C },
    { "TRANS_DDI_FUNC_A", 0x60400 },
    { "DDI_BUF_CTL_A",    0x64000 },
    { "TRANSCONF_A",      0x70008 },
    { "PLANE_CTL_1_A",    0x70180 },
    { "PLANE_STRIDE_1_A", 0x70188 },
    { "PLANE_SIZE_1_A",   0x70190 },
    { "PLANE_SURF_1_A",   0x7019C },
};

bool CoreUltraGraphicsDriver::init(OSDictionary *dict)
{
    if (!super::init(dict)) return false;
    pciDevice = nullptr;
    mmioMap = nullptr;
    mmioBase = nullptr;
    mmioLength = 0;
    scratchDesc = nullptr;
    scratchVirt = nullptr;
    scratchPhys = 0;
    scratchSize = 0;
    fbMemory = nullptr;
    fbMap = nullptr;
    fbPhys = 0;
    fbWidth = fbHeight = fbDepth = fbPitch = fbBytesPerRow = 0;
    return true;
}

void CoreUltraGraphicsDriver::free()
{
    releaseResources();
    super::free();
}

IOService *CoreUltraGraphicsDriver::probe(IOService *provider, SInt32 *score)
{
    IOPCIDevice *pci = OSDynamicCast(IOPCIDevice, provider);
    if (!pci) return nullptr;

    UInt16 vendor = pci->configRead16(kIOPCIConfigVendorID);
    UInt16 device = pci->configRead16(kIOPCIConfigDeviceID);
    if (vendor != 0x8086 || device != 0x7D45) return nullptr;

    *score = 5000;
    return this;
}

uint32_t CoreUltraGraphicsDriver::readReg(uint32_t offset) const
{
    if (!mmioBase || mmioLength < 4 || offset > mmioLength - 4) return 0xFFFFFFFFu;
    return OSReadLittleInt32((const volatile void *)mmioBase, offset);
}

void CoreUltraGraphicsDriver::writeReg(uint32_t offset, uint32_t value)
{
    if (!mmioBase || mmioLength < 4 || offset > mmioLength - 4) return;
    OSWriteLittleInt32((volatile void *)((uint8_t *)mmioBase + offset), 0, value);
}

void CoreUltraGraphicsDriver::logPciIdentity()
{
    UInt16 vendor   = pciDevice->configRead16(kIOPCIConfigVendorID);
    UInt16 device   = pciDevice->configRead16(kIOPCIConfigDeviceID);
    UInt8  revision = pciDevice->configRead8(kIOPCIConfigRevisionID);
    UInt16 command  = pciDevice->configRead16(kIOPCIConfigCommand);
    UInt32 bar0     = pciDevice->configRead32(kIOPCIConfigBaseAddress0);
    IOLog("CoreUltraGraphics: PCI vendor 0x%04x device 0x%04x rev 0x%02x cmd 0x%04x BAR0 0x%08x\n",
          (unsigned)vendor, (unsigned)device, (unsigned)revision, (unsigned)command, (unsigned)bar0);
}

void CoreUltraGraphicsDriver::dumpDisplayState()
{
    for (unsigned i = 0; i < sizeof(kDumpRegs) / sizeof(kDumpRegs[0]); i++) {
        IOLog("CoreUltraGraphics: %s [0x%05x] = 0x%08x\n",
              kDumpRegs[i].name, (unsigned)kDumpRegs[i].offset,
              (unsigned)readReg(kDumpRegs[i].offset));
    }
    uint32_t src = readReg(PIPE_SRC_A_OFFSET);
    if (src != 0xFFFFFFFFu && src != 0) {
        IOLog("CoreUltraGraphics: PIPE_SRC_A decodes to %ux%u\n",
              (unsigned)(((src >> 16) & 0x1FFF) + 1), (unsigned)((src & 0x1FFF) + 1));
    }
}

void CoreUltraGraphicsDriver::releaseScratchBuffer()
{
    if (scratchDesc) {
        scratchDesc->complete();
        scratchDesc->release();
        scratchDesc = nullptr;
    }
    scratchVirt = nullptr;
    scratchPhys = 0;
    scratchSize = 0;
}

void CoreUltraGraphicsDriver::releaseResources()
{
    releaseScratchBuffer();
    if (fbMap) { fbMap->release(); fbMap = nullptr; }
    if (fbMemory) { fbMemory->complete(); fbMemory->release(); fbMemory = nullptr; }
    fbPhys = 0;
    mmioBase = nullptr;
    mmioLength = 0;
    if (mmioMap) { mmioMap->release(); mmioMap = nullptr; }
    if (pciDevice) { pciDevice->release(); pciDevice = nullptr; }
}

bool CoreUltraGraphicsDriver::start(IOService *provider)
{
    if (!super::start(provider)) return false;

    pciDevice = OSDynamicCast(IOPCIDevice, provider);
    if (!pciDevice) {
        IOLog("CoreUltraGraphics: provider is not an IOPCIDevice\n");
        return false;
    }
    pciDevice->retain();

    logPciIdentity();

    pciDevice->setMemoryEnable(true);

    IOMemoryMap *map = pciDevice->mapDeviceMemoryWithIndex(0);
    if (!map) {
        IOLog("CoreUltraGraphics: failed to map device memory index 0\n");
        releaseResources();
        return false;
    }
    mmioMap = map;
    mmioBase = (volatile void *)mmioMap->getVirtualAddress();
    mmioLength = (UInt32)mmioMap->getLength();
    IOLog("CoreUltraGraphics: MMIO mapped phys 0x%llx virt %p len 0x%x\n",
          (unsigned long long)mmioMap->getPhysicalAddress(), mmioBase, (unsigned)mmioLength);

    if (mmioLength < 0x80000) {
        IOLog("CoreUltraGraphics: warning: mapping is smaller than expected (0x%x)\n", (unsigned)mmioLength);
    }

    dumpDisplayState();

    if (!initDisplayEngine()) {
        IOLog("CoreUltraGraphics: failed to initialize display engine\n");
        releaseResources();
        return false;
    }

    if (!initFramebuffer()) {
        IOLog("CoreUltraGraphics: failed to initialize framebuffer\n");
        releaseResources();
        return false;
    }

    if (!allocateHardwareScratchBuffer(64 * 1024)) {
        IOLog("CoreUltraGraphics: warning: failed to allocate scratch buffer\n");
    }

    registerService();
    return true;
}

bool CoreUltraGraphicsDriver::initDisplayEngine()
{
    // Power well enable for display (Gen12 PWR_WELL_CTL1)
    uint32_t pwr = readReg(PWR_WELL_CTL1);
    if (!(pwr & (1u << 31))) {
        writeReg(PWR_WELL_CTL1, pwr | (1u << 31));
        IOSleep(10);
        IOLog("CoreUltraGraphics: enabled display power well\n");
    }

    // Basic pipe timing (assume 1920x1080 @ 60Hz for now)
    // HTOTAL_A, VTOTAL_A, PIPE_SRC_A, etc. would be programmed here
    // based on detected panel EDID

    return true;
}

bool CoreUltraGraphicsDriver::initFramebuffer()
{
    // Default to 1920x1080 @ 32bpp
    fbWidth = 1920;
    fbHeight = 1080;
    fbDepth = 32;
    fbBytesPerRow = fbWidth * (fbDepth / 8);
    fbPitch = fbBytesPerRow;
    UInt32 fbSize = fbHeight * fbPitch;

    fbMemory = IOBufferMemoryDescriptor::inTaskWithPhysicalMask(
        kernel_task, kIOMemoryUnshared | kIOMemoryPhysicallyContiguous, fbSize, 0x00000000FFFFF000ULL);
    if (!fbMemory) return false;

    if (fbMemory->prepare() != kIOReturnSuccess) {
        fbMemory->release();
        fbMemory = nullptr;
        return false;
    }

    fbMap = fbMemory->map(kIOMapWriteCombineCache);
    if (!fbMap) {
        fbMemory->complete();
        fbMemory->release();
        fbMemory = nullptr;
        return false;
    }

    fbPhys = fbMemory->getPhysicalAddress();
    fbVirt = fbMap->getVirtualAddress();
    bzero(fbVirt, fbSize);

    IOLog("CoreUltraGraphics: framebuffer %ux%u @ %dbpp, phys 0x%llx virt %p\n",
          fbWidth, fbHeight, fbDepth, (unsigned long long)fbPhys, fbVirt);

    // Program plane 1A for primary display
    writeReg(PLANE_STRIDE_1_A, fbPitch);
    writeReg(PLANE_SIZE_1_A, ((fbHeight - 1) << 16) | (fbWidth - 1));
    writeReg(PLANE_SURF_1_A, (uint32_t)(fbPhys & 0xFFFFFFFF));
    uint32_t ctl = readReg(PLANE_CTL_1_A);
    writeReg(PLANE_CTL_1_A, ctl | PLANE_CTL_EN | (1u << 10)); // enable + alpha

    // Initialize IOFramebuffer
    setFramebufferDepth(fbDepth);
    setFramebufferWidth(fbWidth);
    setFramebufferHeight(fbHeight);
    setFramebufferBytesPerRow(fbBytesPerRow);
    setFramebufferAddress(fbVirt);

    return true;
}

void CoreUltraGraphicsDriver::stop(IOService *provider)
{
    releaseResources();
    super::stop(provider);
}

// IOFramebuffer overrides
IOReturn CoreUltraGraphicsDriver::setDisplayMode(IOIndex depth, IOIndex width, IOIndex height, IOOptionBits flags)
{
    if (depth != 32 || width != fbWidth || height != fbHeight) {
        return kIOReturnUnsupported;
    }
    return kIOReturnSuccess;
}

IOReturn CoreUltraGraphicsDriver::getDisplayMode(IOIndex *depth, IOIndex *width, IOIndex *height, IOOptionBits *flags)
{
    if (depth) *depth = fbDepth;
    if (width) *width = fbWidth;
    if (height) *height = fbHeight;
    if (flags) *flags = 0;
    return kIOReturnSuccess;
}

IOReturn CoreUltraGraphicsDriver::setDisplayMode(IOItemCount depth, IOItemCount width, IOItemCount height, IOOptionBits flags)
{
    return setDisplayMode((IOIndex)depth, (IOIndex)width, (IOIndex)height, flags);
}

IOReturn CoreUltraGraphicsDriver::getPixelInformation(IOIndex *bytesPerRow, IOIndex *bytesPerPixel, IOIndex *bitsPerPixel, IOIndex *pixelsPerRow)
{
    if (bytesPerRow) *bytesPerRow = fbBytesPerRow;
    if (bytesPerPixel) *bytesPerPixel = fbDepth / 8;
    if (bitsPerPixel) *bitsPerPixel = fbDepth;
    if (pixelsPerRow) *pixelsPerRow = fbWidth;
    return kIOReturnSuccess;
}

IOReturn CoreUltraGraphicsDriver::flushDisplay(IOOptionBits options)
{
    flush();
    return kIOReturnSuccess;
}

void CoreUltraGraphicsDriver::flush()
{
    // Memory barrier to ensure writes are visible to display engine
    asm volatile("mfence" ::: "memory");
    // Display engine reads from fbVirt directly via PLANE_SURF_1_A
}

bool CoreUltraGraphicsDriver::allocateHardwareScratchBuffer(uint32_t size)
{
    if (scratchDesc || size == 0 || size > (16u << 20)) return false;
    size = (size + 4095u) & ~4095u;

    IOBufferMemoryDescriptor *desc = IOBufferMemoryDescriptor::inTaskWithPhysicalMask(
        kernel_task, kIODirectionInOut | kIOMemoryPhysicallyContiguous, size, 0x00000000FFFFF000ULL);
    if (!desc) return false;
    if (desc->prepare() != kIOReturnSuccess) { desc->release(); return false; }

    void *virt = desc->getBytesNoCopy();
    IOPhysicalAddress phys = desc->getPhysicalAddress();
    if (!virt || !phys) { desc->complete(); desc->release(); return false; }

    bzero(virt, size);
    scratchDesc = desc;
    scratchVirt = virt;
    scratchPhys = phys;
    scratchSize = size;
    return true;
}