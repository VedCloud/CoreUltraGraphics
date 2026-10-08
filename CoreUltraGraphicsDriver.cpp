#include "CoreUltraGraphicsDriver.h"

#define super IOService
OSDefineMetaClassAndStructors(CoreUltraGraphicsDriver, IOService);

bool CoreUltraGraphicsDriver::init(OSDictionary *dict)
{
    if (!super::init(dict)) return false;
    pciDevice = nullptr;
    mmioMap = nullptr;
    mmioBase = nullptr;
    mmioLength = 0;
    return true;
}

void CoreUltraGraphicsDriver::free()
{
    super::free();
}

IOService *CoreUltraGraphicsDriver::probe(IOService *provider, SInt32 *score)
{
    return super::probe(provider, score);
}

bool CoreUltraGraphicsDriver::start(IOService *provider)
{
    if (!super::start(provider)) return false;
    pciDevice = OSDynamicCast(IOPCIDevice, provider);
    if (!pciDevice) return false;
    pciDevice->retain();
    pciDevice->setMemoryEnable(true);
    pciDevice->setBusMasterEnable(true);
    IOMemoryMap *map = pciDevice->mapDeviceMemoryWithIndex(0);
    if (!map) { pciDevice->release(); pciDevice = nullptr; return false; }
    mmioMap = map;
    mmioBase = (volatile void *)mmioMap->getVirtualAddress();
    mmioLength = (UInt32)mmioMap->getLength();
    registerService();
    return true;
}

void CoreUltraGraphicsDriver::stop(IOService *provider)
{
    if (mmioMap) { mmioMap->release(); mmioMap = nullptr; }
    if (pciDevice) { pciDevice->release(); pciDevice = nullptr; }
    super::stop(provider);
}
