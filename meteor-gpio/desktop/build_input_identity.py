"""Keep Wacom identity; give the physical ELAN its own virtual trackpad identity."""
from pathlib import Path
import subprocess,plistlib
root=Path.cwd();src=root/'.deps/VoodooInput';sdk=root/'.deps/MacKernelSDK';out=root/'ci-diagnostics'
helper='''static UInt32 latitudeInputLocation(const IORegistryEntry *device) {
    const IORegistryEntry *entry = device;
    for (unsigned depth = 0; entry && depth < 12; ++depth) {
        OSNumber *vendor = OSDynamicCast(OSNumber, entry->getProperty("VendorID"));
        OSNumber *product = OSDynamicCast(OSNumber, entry->getProperty("ProductID"));
        if (vendor && product && vendor->unsigned32BitValue() == 0x04f3 &&
            product->unsigned32BitValue() == 0x328e)
            return 0x14500000;
        entry = entry->getParentEntry(gIOServicePlane);
    }
    return 0x14400000;
}
'''
for name in ['VoodooInputSimulatorDevice','VoodooInputActuatorDevice']:
    p=src/('VoodooInput/VoodooInputSimulator/'+name+'.cpp');s=p.read_text()
    anchor='OSNumber* '+name+'::newLocationIDNumber() const {'
    assert s.count(anchor)==1
    s=s.replace(anchor,helper+'\n'+anchor)
    old='    return OSNumber::withNumber(0x14400000, 32);'
    assert s.count(old)==1
    s=s.replace(old,'    return OSNumber::withNumber(latitudeInputLocation(this), 32);')
    p.write_text(s)
    (out/(name+'-identity.cpp')).write_text(s)
# Exercise the exact ancestor-selection helper with mock registry objects.
test=out/'identity-test.cpp'
test.write_text('''#include <cassert>
#include <cstdint>
#include <cstring>
using UInt32 = uint32_t;
struct OSObject { virtual ~OSObject() = default; };
struct OSNumber : OSObject { UInt32 v; OSNumber(UInt32 n):v(n){} UInt32 unsigned32BitValue(){return v;} };
const char *gIOServicePlane = "IOService";
struct IORegistryEntry {
    OSNumber vendor,product; const IORegistryEntry *parent;
    IORegistryEntry(UInt32 v, UInt32 p, const IORegistryEntry *up=nullptr):vendor(v),product(p),parent(up){}
    OSObject *getProperty(const char *k) const { return const_cast<OSNumber*>(std::strcmp(k,"VendorID")==0?&vendor:&product); }
    const IORegistryEntry *getParentEntry(const char *) const {return parent;}
};
#define OSDynamicCast(type,value) dynamic_cast<type*>(value)
'''+helper+'''
int main() {
 IORegistryEntry wacom(0x56a,0x4a19),elan(0x4f3,0x328e),other(0x4f3,0x1234);
 IORegistryEntry simulated_wacom(0x5ac,0x281,&wacom),simulated_elan(0x5ac,0x281,&elan);
 assert(latitudeInputLocation(&simulated_wacom)==0x14400000);
 assert(latitudeInputLocation(&simulated_elan)==0x14500000);
 assert(latitudeInputLocation(&other)==0x14400000);
 assert(latitudeInputLocation(nullptr)==0x14400000);
}
''')
subprocess.run(['clang++','-std=c++17',str(test),'-o',str(out/'identity-test')],check=True)
subprocess.run([str(out/'identity-test')],check=True)
macsdk=subprocess.check_output(['xcrun','--sdk','macosx','--show-sdk-path'],text=True).strip()
flags=['-arch','x86_64','-mmacosx-version-min=10.12','-nostdinc','-DKERNEL','-DAPPLE','-DNeXT',
       '-D__ACIDANTHERA_MAC_SDK','-O2','-mkernel','-fno-builtin','-isysroot',macsdk,'-isystem',str(sdk/'Headers')]
flags+=['-I'+str(p) for p in sorted({p.parent for p in src.rglob('*.hpp')}|{p.parent for p in src.rglob('*.h')})]
objs=[];objdir=out/'identity-objects';objdir.mkdir(exist_ok=True)
for p in sorted((src/'VoodooInput').rglob('*.cpp')):
    obj=objdir/(p.stem+'.o')
    subprocess.run(['xcrun','clang++','-std=gnu++17','-fno-rtti','-fno-exceptions','-fapple-kext',*flags,
                    '-c',str(p),'-o',str(obj)],check=True);objs.append(str(obj))
meta=objdir/'meta.c';meta.write_text('''#include <mach/mach_types.h>
#include <mach/kmod.h>
extern kern_return_t _start(kmod_info_t *, void *);
extern kern_return_t _stop(kmod_info_t *, void *);
KMOD_EXPLICIT_DECL("me.kishorprins.VoodooInput", "1.1.7", _start, _stop)
__private_extern__ kmod_start_func_t *_realmain = 0;
__private_extern__ kmod_stop_func_t *_antimain = 0;
''')
subprocess.run(['xcrun','clang',*flags,'-c',str(meta),'-o',str(objdir/'meta.o')],check=True)
binary=out/'VoodooInput.kext/Contents/MacOS/VoodooInput';binary.parent.mkdir(parents=True,exist_ok=True)
subprocess.run(['xcrun','clang++','-arch','x86_64','-isysroot',macsdk,'-mkernel','-fapple-kext','-static',
                '-nostdlib','-L'+str(sdk/'Library/x86_64'),'-Xlinker','-kext','-Xlinker','-no_deduplicate',
                *objs,'-lkmodc++',str(objdir/'meta.o'),'-lkmod','-lcc_kext','-o',str(binary)],check=True)
assert '_kmod_info' in subprocess.check_output(['nm','-gU',str(binary)],text=True)
print('Distinct ELAN identity compiled; exact-helper Wacom/ELAN/unknown/null tests passed.')
