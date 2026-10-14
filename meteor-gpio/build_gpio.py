from pathlib import Path
import plistlib
import shutil
import subprocess

here=Path(__file__).resolve().parent
source=Path('.deps/VoodooGPIO/VoodooGPIO')
sdk=Path('.deps/MacKernelSDK').resolve()
for name in ['VoodooGPIOIntel.hpp','VoodooGPIOIntel.cpp']:
    shutil.copy2(here/name,source/name)
platform=source/'MeteorLake-P'
platform.mkdir(exist_ok=True)
for name in ['VoodooGPIOMeteorLakeP.hpp','VoodooGPIOMeteorLakeP.cpp']:
    shutil.copy2(here/name,platform/name)
info=plistlib.loads((here/'Info.plist').read_bytes())
info.update(CFBundleExecutable='VoodooGPIO',CFBundleIdentifier='org.coolstar.VoodooGPIO',CFBundleName='VoodooGPIO',CFBundleVersion='1.2.0',CFBundleShortVersionString='1.2.0')
build=Path('ci-results')
build.mkdir(exist_ok=True)
objects=build/'objects'
objects.mkdir(exist_ok=True)
macsdk=subprocess.check_output(['xcrun','--sdk','macosx','--show-sdk-path'],text=True).strip()
common=['-arch','x86_64','-mmacosx-version-min=10.12','-fno-builtin','-fno-exceptions','-fno-rtti','-nostdinc','-DKERNEL','-DAPPLE','-DNeXT','-O2','-mkernel','-fapple-kext','-Wno-deprecated-declarations','-isysroot',macsdk,'-isystem',str(sdk/'Headers')]
objpaths=[]
for file in sorted(source.rglob('*.cpp')):
    obj=objects/(file.relative_to(source).as_posix().replace('/','_')+'.o')
    print('Compiling',file,flush=True)
    subprocess.run(['xcrun','clang++','-std=gnu++17',*common,'-c',str(file),'-o',str(obj)],check=True)
    objpaths.append(str(obj))
metadata=build/'kmod_info.c'
metadata.write_text('''#include <mach/mach_types.h>
#include <mach/kmod.h>
extern kern_return_t _start(kmod_info_t *, void *);
extern kern_return_t _stop(kmod_info_t *, void *);
KMOD_EXPLICIT_DECL("org.coolstar.VoodooGPIO", "1.2.0", _start, _stop)
__private_extern__ kmod_start_func_t *_realmain = 0;
__private_extern__ kmod_stop_func_t *_antimain = 0;
''')
meta=objects/'kmod_info.o'
cflags=[a for a in common if a not in ['-fno-exceptions','-fno-rtti','-fapple-kext']]
subprocess.run(['xcrun','clang',*cflags,'-c',str(metadata),'-o',str(meta)],check=True)
bundle=build/'VoodooGPIO.kext'
binary=bundle/'Contents/MacOS/VoodooGPIO'
binary.parent.mkdir(parents=True,exist_ok=True)
subprocess.run(['xcrun','clang++','-arch','x86_64','-isysroot',macsdk,'-mkernel','-fapple-kext','-static','-nostdlib','-L'+str(sdk/'Library/x86_64'),'-Xlinker','-kext','-Xlinker','-no_deduplicate',*objpaths,'-lkmodc++',str(meta),'-lkmod','-lcc_kext','-o',str(binary)],check=True)
(bundle/'Contents/Info.plist').write_bytes(plistlib.dumps(info,sort_keys=False))
symbols=subprocess.check_output(['nm','-gU',str(binary)],text=True)
assert '_kmod_info' in symbols
assert 'VoodooGPIOMeteorLakeP' in symbols
subprocess.run(['plutil','-lint',str(bundle/'Contents/Info.plist')],check=True)
inspection=subprocess.check_output(['otool','-hv',str(binary)],text=True)
assert 'X86_64' in inspection.upper()
assert 'KEXT' in inspection.upper()
(build/'inspection.txt').write_text(inspection+'\n'+symbols)
shutil.copy2(Path('.deps/VoodooGPIO/LICENSE.md'),build/'VoodooGPIO-LICENSE.md')
print('Compiled x86_64 kext and verified kmod metadata; hardware functionality untested.')
