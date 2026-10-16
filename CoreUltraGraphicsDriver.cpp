#include "CoreUltraGraphicsDriver.h"
#include <IOKit/IOLib.h>
#include <IOKit/IOMemoryDescriptor.h>

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
    setProperty("CoreUltraGraphicsProbeVersion", "0.2.0");
    setProperty("CoreUltraGraphicsProbeStatus", "attached; metadata only");
    setProperty("CoreUltraGraphicsDriverMode", "PCI attachment probe; no GPU register access");
    setProperty("CoreUltraGraphicsAccelerationSupported", false);
    setProperty("CoreUltraGraphicsGuCInitialized", false);
    setProperty("ProbeVendorID", 0x8086, 32);
    setProperty("ProbeDeviceID", 0x7D45, 32);
    setProperty("ProbeRevisionID", revision, 32);
    setProperty("ProbePCICommand", command, 32);
    setProperty("ProbeMemoryResourceCount", resourceCount, 32);

    IOLog("CoreUltraGraphics: attachment probe 0.2.0 on 8086:7D45 revision %02x; metadata only\n",
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
    registerService();
    return true;
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
