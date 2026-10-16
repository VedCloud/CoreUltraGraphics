#include "CoreUltraGraphicsDriver.h"
#include "port/guc_protocol.h"

#define super IOService
OSDefineMetaClassAndStructors(CoreUltraGraphicsDriver, IOService);

// Display-engine registers to log. READ ONLY: nothing in this file writes to the GPU.
// Offsets are the Gen12-style layout used by Linux i915/xe; verify them against the
// display-version-14 sources. A value of 0xFFFFFFFF usually means the register is
// unreachable (power well off) or the offset is wrong for this platform.
struct DumpReg { const char *name; uint32_t offset; };
static const DumpReg kDumpRegs[] = {
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
#define PIPE_SRC_A_OFFSET 0x6001C

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
    return true;
}

void CoreUltraGraphicsDriver::free()
{
    releaseResources();
    super::free();
}

IOService *CoreUltraGraphicsDriver::probe(IOService *provider, SInt32 *score)
{
    IOPCIDevice *device = OSDynamicCast(IOPCIDevice, provider);
    if (!device || device->configRead16(kIOPCIConfigVendorID) != 0x8086 ||
        device->configRead16(kIOPCIConfigDeviceID) != 0x7D45)
        return nullptr;
    return super::probe(provider, score);
}

uint32_t CoreUltraGraphicsDriver::readReg(uint32_t offset) const
{
    if (!mmioBase || mmioLength < 4 || offset > mmioLength - 4) return 0xFFFFFFFFu;
    return OSReadLittleInt32((const volatile void *)mmioBase, offset);
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

bool CoreUltraGraphicsDriver::start(IOService *provider)
{
    if (!super::start(provider)) return false;

    pciDevice = OSDynamicCast(IOPCIDevice, provider);
    if (!pciDevice || pciDevice->configRead16(kIOPCIConfigVendorID) != 0x8086 ||
        pciDevice->configRead16(kIOPCIConfigDeviceID) != 0x7D45) {
        pciDevice = nullptr;
        IOLog("CoreUltraGraphics: provider does not match Intel 8086:7D45\n");
        return false;
    }
    pciDevice->retain();

    logPciIdentity();

    // Memory decode only. Bus mastering is not needed for register access,
    // so it stays off until something actually needs DMA.
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

    setProperty("CoreUltraGraphicsAccelerationSupported", false);
    setProperty("CoreUltraGraphicsDriverMode", "PCI/display diagnostics; GuC transport not initialized");

    registerService();
    return true;
}

void CoreUltraGraphicsDriver::stop(IOService *provider)
{
    releaseResources();
    super::stop(provider);
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
    mmioBase = nullptr;
    mmioLength = 0;
    if (mmioMap) { mmioMap->release(); mmioMap = nullptr; }
    if (pciDevice) { pciDevice->release(); pciDevice = nullptr; }
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
