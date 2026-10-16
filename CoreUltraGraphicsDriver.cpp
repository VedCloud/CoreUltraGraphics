#include "CoreUltraGraphicsDriver.h"
#include <IOKit/IOLib.h>
#include <IOKit/IOMemoryDescriptor.h>
#include <libkern/OSByteOrder.h>
#include "port/mmio_probe_policy.h"

#define super IOService
OSDefineMetaClassAndStructors(CoreUltraGraphicsDriver, IOService);

static bool matchesTarget(IOPCIDevice *device)
{
    return device && device->configRead16(kIOPCIConfigVendorID) == 0x8086 &&
           device->configRead16(kIOPCIConfigDeviceID) == 0x7D45;
}

bool CoreUltraGraphicsDriver::init(OSDictionary *dict)
{
    if (!super::init(dict)) return false;
    pciDevice = nullptr;
    return true;
}

IOService *CoreUltraGraphicsDriver::probe(IOService *provider, SInt32 *score)
{
    if (!matchesTarget(OSDynamicCast(IOPCIDevice, provider))) return nullptr;
    return super::probe(provider, score);
}

bool CoreUltraGraphicsDriver::start(IOService *provider)
{
    IOPCIDevice *device = OSDynamicCast(IOPCIDevice, provider);
    if (!matchesTarget(device) || pciDevice) return false;
    if (!super::start(provider)) return false;
    device->retain();
    pciDevice = device;

    const UInt8 revision = device->configRead8(kIOPCIConfigRevisionID);
    const UInt16 command = device->configRead16(kIOPCIConfigCommand);
    const unsigned int resourceCount = device->getDeviceMemoryCount();
    setProperty("CoreUltraGraphicsProbeVersion", "0.3.0");
    setProperty("CoreUltraGraphicsProbeStatus", "attached; identification pending");
    setProperty("CoreUltraGraphicsDriverMode", "one-shot read-only graphics/media GMD_ID");
    setProperty("CoreUltraGraphicsAccelerationSupported", false);
    setProperty("CoreUltraGraphicsGuCInitialized", false);
    setProperty("ProbeVendorID", 0x8086, 32);
    setProperty("ProbeDeviceID", 0x7D45, 32);
    setProperty("ProbeRevisionID", revision, 32);
    setProperty("ProbePCICommand", command, 32);
    setProperty("ProbeMemoryResourceCount", resourceCount, 32);

    IOLog("CoreUltraGraphics: identification probe 0.3.0 on 8086:7D45 revision %02x\n",
          (unsigned)revision);
    // Inspect existing IOKit descriptors without mapping or dereferencing them.
    // No PCI decode changes, bus-master enablement, GPU MMIO, or DMA allocation.
    const unsigned int count = resourceCount < 8 ? resourceCount : 8;
    for (unsigned int index = 0; index < count; ++index) {
        IOMemoryDescriptor *memory = device->getDeviceMemoryWithIndex(index);
        if (!memory) continue;
        char key[48];
        const UInt64 address = memory->getPhysicalAddress();
        const UInt64 length = memory->getLength();
        snprintf(key, sizeof(key), "ProbeMemory%uPhysicalAddress", index);
        setProperty(key, address, 64);
        snprintf(key, sizeof(key), "ProbeMemory%uLength", index);
        setProperty(key, length, 64);
        IOLog("CoreUltraGraphics: resource %u address 0x%llx length 0x%llx; not mapped\n",
              index, (unsigned long long)address, (unsigned long long)length);
    }
    setProperty("ProbeResourceListTruncated", resourceCount > count);
    readIdentification();
    registerService();
    return true;
}

void CoreUltraGraphicsDriver::publishIdentification(const char *prefix, UInt32 raw)
{
    char key[64];
    snprintf(key, sizeof(key), "%sRaw", prefix);
    setProperty(key, raw, 32);
    snprintf(key, sizeof(key), "%sValid", prefix);
    const bool valid = cug_gmd_value_valid(raw);
    setProperty(key, valid);
    if (!valid) return;
    snprintf(key, sizeof(key), "%sArchitecture", prefix);
    setProperty(key, cug_gmd_arch(raw), 32);
    snprintf(key, sizeof(key), "%sRelease", prefix);
    setProperty(key, cug_gmd_release(raw), 32);
    snprintf(key, sizeof(key), "%sRevision", prefix);
    setProperty(key, cug_gmd_revision(raw), 32);
}

void CoreUltraGraphicsDriver::readIdentification()
{
    // No caller-selected offsets, MMIO stores, forcewake, reset, or DMA.
    setProperty("ProbeMMIOReadCount", static_cast<UInt64>(0), 32);
    setProperty("ProbeMMIOMappingActive", false);
    setProperty("ProbeMMIOWritesPerformed", false);
    setProperty("ProbeForcewakeRequested", false);
    if (!(pciDevice->configRead16(kIOPCIConfigCommand) & 2u)) {
        setProperty("CoreUltraGraphicsProbeStatus", "attached; skipped: memory decode disabled");
        return;
    }
    UInt8 pmOffset = 0;
    const UInt32 pm = pciDevice->findPCICapability(kIOPCIPowerManagementCapability, &pmOffset);
    if (!pm || !pmOffset || pmOffset > 0xf8u) {
        setProperty("CoreUltraGraphicsProbeStatus", "attached; skipped: PCI power state unavailable");
        return;
    }
    const UInt16 pmcsr = pciDevice->configRead16(pmOffset + 4);
    setProperty("ProbePCIPMCSR", pmcsr, 32);
    if ((pmcsr & 3u) != 0u) {
        setProperty("CoreUltraGraphicsProbeStatus", "attached; skipped: PCI device not D0");
        return;
    }
    const UInt32 low = pciDevice->configRead32(kIOPCIConfigBaseAddress0);
    const UInt32 high = pciDevice->configRead32(kIOPCIConfigBaseAddress1);
    const UInt64 bar = (static_cast<UInt64>(high) << 32) | (low & ~0xfull);
    // The measured device has a 64-bit memory BAR0. Reject other layouts.
    if ((low & 7u) != 4u || !bar || bar == 0xfffffffffffffff0ull) {
        setProperty("CoreUltraGraphicsProbeStatus", "attached; skipped: unexpected BAR0 type");
        return;
    }
    IODeviceMemory *memory = pciDevice->getDeviceMemoryWithRegister(kIOPCIConfigBaseAddress0);
    if (!memory || memory->getPhysicalAddress() != bar ||
        memory->getLength() != 0x01000000ull) {
        setProperty("CoreUltraGraphicsProbeStatus", "attached; skipped: BAR0 resource mismatch");
        return;
    }
    IOMemoryMap *mapping = pciDevice->mapDeviceMemoryWithRegister(
        kIOPCIConfigBaseAddress0, kIOMapInhibitCache | kIOMapReadOnly);
    if (!mapping) {
        setProperty("CoreUltraGraphicsProbeStatus", "attached; skipped: BAR0 mapping failed");
        return;
    }
    setProperty("ProbeMMIOMappingActive", true);
    const UInt64 length = mapping->getLength();
    const mach_vm_address_t address = mapping->getVirtualAddress();
    const bool accessible = address && mapping->getPhysicalAddress() == bar &&
        cug_probe_read_allowed(CUG_GRAPHICS_GMD_ID, length) &&
        cug_probe_read_allowed(CUG_MEDIA_GMD_ID, length) &&
        (pciDevice->configRead16(kIOPCIConfigCommand) & 2u) &&
        !(pciDevice->configRead16(pmOffset + 4) & 3u);
    if (accessible) {
        // GMD_ID lies outside forcewake ranges on MTL (Linux v6.12).
        const volatile void *base = reinterpret_cast<const volatile void *>(address);
        const UInt32 graphics = OSReadLittleInt32(base, CUG_GRAPHICS_GMD_ID);
        const UInt32 media = OSReadLittleInt32(base, CUG_MEDIA_GMD_ID);
        setProperty("ProbeMMIOReadCount", 2, 32);
        publishIdentification("ProbeGraphicsGMD", graphics);
        publishIdentification("ProbeMediaGMD", media);
        const bool valid = cug_gmd_value_valid(graphics) && cug_gmd_value_valid(media);
        setProperty("CoreUltraGraphicsProbeStatus", valid ?
                    "attached; GMD identification read" : "attached; GMD returned invalid value");
        IOLog("CoreUltraGraphics: GMD graphics=0x%08x media=0x%08x; read-only\n",
              (unsigned)graphics, (unsigned)media);
    } else {
        setProperty("CoreUltraGraphicsProbeStatus", "attached; skipped: mapping bounds or power changed");
    }
    mapping->release();
    setProperty("ProbeMMIOMappingActive", false);
}

void CoreUltraGraphicsDriver::releaseResources()
{
    if (pciDevice) {
        pciDevice->release();
        pciDevice = nullptr;
    }
}

void CoreUltraGraphicsDriver::stop(IOService *provider)
{
    setProperty("CoreUltraGraphicsProbeStatus", "stopped");
    releaseResources();
    super::stop(provider);
}

void CoreUltraGraphicsDriver::free()
{
    releaseResources();
    super::free();
}
