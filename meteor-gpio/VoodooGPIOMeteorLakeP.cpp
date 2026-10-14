#include "VoodooGPIOMeteorLakeP.hpp"
OSDefineMetaClassAndStructors(VoodooGPIOMeteorLakeP, VoodooGPIOIntel);
bool VoodooGPIOMeteorLakeP::start(IOService *provider) {
    pins = mtlp_pins; npins = ARRAY_SIZE(mtlp_pins);
    groups = nullptr; ngroups = 0;
    functions = nullptr; nfunctions = 0;
    communities = mtlp_communities; ncommunities = ARRAY_SIZE(mtlp_communities);
    IOLog("%s::Loading experimental Meteor Lake-P GPIO data\n", getName());
    return VoodooGPIOIntel::start(provider);
}
