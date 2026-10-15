#include "LatitudeI2CCompletion.hpp"
#include <cassert>
#include <cstdio>
#include <vector>

int main() {
    unsigned last, waited, sleeps=0, elapsed=0, index=0;
    auto delay=[&](unsigned us) { ++sleeps; elapsed+=us; };
    assert(latitudeWaitMasterIdle([] { return 6U; },delay,last,waited));
    assert(sleeps==0 && waited==0);
    std::vector<unsigned> statuses={0x23,0x23,0x6};
    assert(latitudeWaitMasterIdle([&] { return statuses[index++]; },delay,last,waited));
    assert(index==3 && waited==2200 && last==6);
    sleeps=elapsed=0;
    assert(!latitudeWaitMasterIdle([] { return 0x23U; },delay,last,waited));
    assert(waited==20000 && elapsed==20000 && sleeps==19);
    sleeps=0;
    assert(!latitudeWaitMasterIdle([] { return 0xffffffffU; },delay,last,waited));
    assert(sleeps==0 && waited==0);
    assert(latitudeTransferComplete(0,1,1,1,0,true));
    assert(latitudeTransferComplete(0,2,2,2,0,true));
    assert(latitudeTransferComplete(0,1,1,0,0,false));
    assert(!latitudeTransferComplete(1,1,1,1,0,true));
    assert(!latitudeTransferComplete(2,1,1,1,0,true));
    assert(!latitudeTransferComplete(0,0,1,1,0,true));
    assert(!latitudeTransferComplete(0,1,1,0,0,true));
    assert(!latitudeTransferComplete(0,1,1,1,1,true));
    assert(!latitudeTransferComplete(0,1,1,1,-1,true));
    assert(!latitudeTransferComplete(0,0,0,0,0,false));
    puts("I2C completion: 14 regression cases passed");
}
