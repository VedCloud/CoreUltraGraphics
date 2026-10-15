from pathlib import Path
import plistlib,subprocess,hashlib,json,shutil
root=Path.cwd();out=root/'ci-diagnostics';sdk=root/'.deps/MacKernelSDK'
lilu=root/'.deps/Lilu';brcm=root/'.deps/BrcmPatchRAM'
macsdk=subprocess.check_output(['xcrun','--sdk','macosx','--show-sdk-path'],text=True).strip()
objects=out/'bluetool-objects';objects.mkdir(exist_ok=True)
flags=['-arch','x86_64','-mmacosx-version-min=10.15','-nostdinc','-DKERNEL','-DAPPLE','-DNeXT',
 '-DDEBUG=1','-DPRODUCT_NAME=BlueToolFixup','-DMODULE_VERSION=2.7.3','-DLILU_CUSTOM_IOKIT_INIT',
 '-D__ACIDANTHERA_MAC_SDK','-O2','-mkernel','-fno-builtin','-isysroot',macsdk,
 '-isystem',str(sdk/'Headers'),'-I',str(lilu/'Lilu')]
objs=[]
for source in [brcm/'BrcmPatchRAM/BlueToolFixup.cpp',lilu/'Lilu/Library/plugin_start.cpp']:
 obj=objects/(source.stem+'.o')
 subprocess.run(['xcrun','clang++','-std=gnu++17','-fno-rtti','-fno-exceptions','-fapple-kext',
  *flags,'-c',str(source),'-o',str(obj)],check=True);objs.append(str(obj))
meta=objects/'kmod_info.c'
meta.write_text('''#include <mach/mach_types.h>
#include <mach/kmod.h>
extern kern_return_t BlueToolFixup_kern_start(kmod_info_t *, void *);
extern kern_return_t BlueToolFixup_kern_stop(kmod_info_t *, void *);
KMOD_EXPLICIT_DECL("as.acidanthera.BlueToolFixup", "2.7.3", BlueToolFixup_kern_start, BlueToolFixup_kern_stop)
__private_extern__ kmod_start_func_t *_realmain = 0;
__private_extern__ kmod_stop_func_t *_antimain = 0;
''')
subprocess.run(['xcrun','clang',*flags,'-c',str(meta),'-o',str(objects/'meta.o')],check=True)
bundle=out/'BlueToolFixup.kext';binary=bundle/'Contents/MacOS/BlueToolFixup'
binary.parent.mkdir(parents=True,exist_ok=True)
subprocess.run(['xcrun','clang++','-arch','x86_64','-isysroot',macsdk,'-mkernel','-fapple-kext','-static',
 '-nostdlib','-L'+str(sdk/'Library/x86_64'),'-Xlinker','-kext','-Xlinker','-no_deduplicate',
 *objs,'-lkmodc++',str(objects/'meta.o'),'-lkmod','-lcc_kext','-o',str(binary)],check=True)
info=plistlib.loads((brcm/'BrcmPatchRAM/BlueToolFixup-Info.plist').read_bytes())
info.update(CFBundleIdentifier='as.acidanthera.BlueToolFixup',CFBundleExecutable='BlueToolFixup',
 CFBundleName='BlueToolFixup',CFBundleVersion='2.7.3',CFBundleShortVersionString='2.7.3')
(bundle/'Contents/Info.plist').write_bytes(plistlib.dumps(info,sort_keys=False))
assert b'found string to patch' in binary.read_bytes()
assert '_kmod_info' in subprocess.check_output(['nm','-gU',str(binary)],text=True)
subprocess.run(['plutil','-lint',str(bundle/'Contents/Info.plist')],check=True)
shutil.copy2(brcm/'LICENSE',out/'BlueToolFixup-LICENSE')
(out/'bluetool-debug-sha256.txt').write_text(hashlib.sha256(binary.read_bytes()).hexdigest()+'\n')
print('Pinned upstream BlueToolFixup2.7.3 DEBUG compiled without changing its patch logic.')
