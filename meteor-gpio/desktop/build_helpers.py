from pathlib import Path
import plistlib, subprocess, shutil, hashlib, json

root=Path.cwd()
src=root/'meteor-gpio/desktop'
out=root/'ci-diagnostics/DesktopTools'
out.mkdir(parents=True,exist_ok=True)
sdk=root/'.deps/MacKernelSDK'
macsdk=subprocess.check_output(['xcrun','--sdk','macosx','--show-sdk-path'],text=True).strip()
subprocess.run(['xcrun','clang','-arch','x86_64','-mmacosx-version-min=10.15','-fobjc-arc',
    '-Wno-deprecated-declarations',str(src/'CameraProbe.m'),'-framework','Foundation',
    '-framework','AVFoundation','-framework','CoreMedia','-framework','CoreVideo',
    '-framework','ImageIO','-framework','ApplicationServices',
    '-Wl,-sectcreate,__TEXT,__info_plist,'+str(src/'CameraProbe-Info.plist'),
    '-o',str(out/'CameraProbe')],check=True)
subprocess.run(['codesign','--force','--sign','-','--identifier','com.ved.latitude.CameraProbe',str(out/'CameraProbe')],check=True)
subprocess.run(['xcrun','clang','-arch','x86_64','-mmacosx-version-min=10.15',str(src/'BacklightProbe.c'),
    '-framework','IOKit','-framework','CoreFoundation','-o',str(out/'BacklightProbe')],check=True)

objects=root/'ci-diagnostics/backlight-objects'
objects.mkdir(exist_ok=True)
flags=['-arch','x86_64','-mmacosx-version-min=10.15','-nostdinc','-DKERNEL','-DAPPLE','-DNeXT',
       '-O2','-mkernel','-fno-builtin','-isysroot',macsdk,'-isystem',str(sdk/'Headers')]
subprocess.run(['xcrun','clang++','-std=gnu++17','-fno-rtti','-fno-exceptions','-fapple-kext',
    *flags,'-c',str(src/'LatitudeBacklightProbe.cpp'),'-o',str(objects/'probe.o')],check=True)
meta=objects/'kmod_info.c'
meta.write_text('''#include <mach/mach_types.h>
#include <mach/kmod.h>
extern kern_return_t _start(kmod_info_t *, void *);
extern kern_return_t _stop(kmod_info_t *, void *);
KMOD_EXPLICIT_DECL("com.ved.latitude.BacklightProbe", "0.1.0", _start, _stop)
__private_extern__ kmod_start_func_t *_realmain = 0;
__private_extern__ kmod_stop_func_t *_antimain = 0;
''')
subprocess.run(['xcrun','clang',*flags,'-c',str(meta),'-o',str(objects/'meta.o')],check=True)
bundle=root/'ci-diagnostics/LatitudeBacklightProbe.kext'
binary=bundle/'Contents/MacOS/LatitudeBacklightProbe'
binary.parent.mkdir(parents=True,exist_ok=True)
subprocess.run(['xcrun','clang++','-arch','x86_64','-isysroot',macsdk,'-mkernel','-fapple-kext','-static',
    '-nostdlib','-L'+str(sdk/'Library/x86_64'),'-Xlinker','-kext','-Xlinker','-no_deduplicate',
    str(objects/'probe.o'),'-lkmodc++',str(objects/'meta.o'),'-lkmod','-lcc_kext','-o',str(binary)],check=True)
info={'CFBundleIdentifier':'com.ved.latitude.BacklightProbe','CFBundleName':'LatitudeBacklightProbe',
      'CFBundleExecutable':'LatitudeBacklightProbe','CFBundleVersion':'0.1.0','CFBundlePackageType':'KEXT',
      'OSBundleRequired':'Root','IOKitPersonalities':{'LatitudeBacklightProbe':{
          'CFBundleIdentifier':'com.ved.latitude.BacklightProbe','IOClass':'LatitudeBacklightProbe',
          'IOProviderClass':'IOPCIDevice','IOPCIMatch':'0x7d458086',
          'IOMatchCategory':'LatitudeBacklightProbe','IOUserClientClass':'LatitudeBacklightClient'}},
      'OSBundleLibraries':{'com.apple.iokit.IOACPIFamily':'1.0.0','com.apple.iokit.IOPCIFamily':'2.9',
          'com.apple.kpi.iokit':'16.0.0','com.apple.kpi.libkern':'16.0.0',
          'com.apple.kpi.bsd':'16.0.0','com.apple.kpi.mach':'16.0.0'}}
(bundle/'Contents/Info.plist').write_bytes(plistlib.dumps(info,sort_keys=False))
symbols=subprocess.check_output(['nm','-gU',str(binary)],text=True)
assert '_kmod_info' in symbols and 'LatitudeBacklightClient' in symbols
for p in [binary,out/'CameraProbe',out/'BacklightProbe']:
    h=subprocess.check_output(['otool','-hv',str(p)],text=True)
    assert 'X86_64' in h.upper()
    if p==binary:assert 'KEXT' in h.upper()
subprocess.run(['plutil','-lint',str(bundle/'Contents/Info.plist')],check=True)
(root/'ci-diagnostics/helpers-sha256.json').write_text(json.dumps({str(p.relative_to(root/'ci-diagnostics')):
    hashlib.sha256(p.read_bytes()).hexdigest() for p in [binary,out/'CameraProbe',out/'BacklightProbe']},indent=2))
print('Camera CPU probe and manual backlight bridge compiled; hardware behavior untested.')
