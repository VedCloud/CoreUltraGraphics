#include "CoreUltraGraphicsDriver.h"
#define super IOService
OSDefineMetaClassAndStructors(CoreUltraGraphicsDriver, IOService);

static bool matchesTarget(IOPCIDevice *device) {
    return device && device->configRead16(kIOPCIConfigVendorID) == 0x8086 &&
           device->configRead16(kIOPCIConfigDeviceID) == 0x7D45;
}

bool CoreUltraGraphicsDriver::init(OSDictionary *dict) {
    if (!super::init(dict)) return false;
    pciDevice = nullptr;
    return true;
}

IOService *CoreUltraGraphicsDriver::probe(IOService *provider, SInt32 *score) {
    if (!matchesTarget(OSDynamicCast(IOPCIDevice, provider))) return nullptr;
    return super::probe(provider, score);
}

bool CoreUltraGraphicsDriver::start(IOService *provider) {
    IOPCIDevice *device = OSDynamicCast(IOPCIDevice, provider);
    if (!matchesTarget(device) || pciDevice) return false;
    if (!super::start(provider)) return false;
    device->retain();
    pciDevice = device;
    IOLog("CoreUltraGraphics: identification probe 8086:7D45 revision %02x; no acceleration\n",
          (unsigned)device->configRead8(kIOPCIConfigRevisionID));
    registerService();
    return true;
}

void CoreUltraGraphicsDriver::releaseResources() {
    if (pciDevice) { pciDevice->release(); pciDevice = nullptr; }
}

void CoreUltraGraphicsDriver::stop(IOService *provider) {
    releaseResources();
    super::stop(provider);
}

void CoreUltraGraphicsDriver::free() {
    releaseResources();
    super::free();
}
