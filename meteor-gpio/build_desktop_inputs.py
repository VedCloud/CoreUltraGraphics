from pathlib import Path
import plistlib
import re
import shutil
import subprocess
from apply_report_fixes import apply
from apply_initialization_fixes import apply as apply_initialization
from apply_touchpad_fixes import apply as apply_touchpad

root=Path.cwd()
i2c=root/'.deps/VoodooI2C'
wifi=root/'.deps/itlwm'
sdk=root/'.deps/MacKernelSDK'
out=root/'ci-diagnostics'
out.mkdir(exist_ok=True)

def replace_once(text,old,new):
    assert text.count(old)==1,(old,text.count(old))
    return text.replace(old,new)

nub=i2c/'VoodooI2C/VoodooI2C/VoodooI2CDevice/VoodooI2CDeviceNub.cpp'
s=nub.read_text()
s=replace_once(s,'    parseResourcesCRS(&crs_parser);\n    parseResourcesDSM(&dsm_parser);','''    IOReturn latitude_crs = parseResourcesCRS(&crs_parser);
    IOReturn latitude_dsm = parseResourcesDSM(&dsm_parser);
    acpi_device->setProperty("LatitudeI2C-CRSStatus", (uint32_t)latitude_crs, 32);
    acpi_device->setProperty("LatitudeI2C-DSMStatus", (uint32_t)latitude_dsm, 32);
    acpi_device->setProperty("LatitudeI2C-CRSHasI2C", crs_parser.found_i2c);
    acpi_device->setProperty("LatitudeI2C-DSMHasI2C", dsm_parser.found_i2c);
    acpi_device->setProperty("LatitudeI2C-DSMHasGPIO", dsm_parser.found_gpio_interrupts);
    OSObject *latitude_buffer = nullptr;
    if (acpi_device->evaluateObject("SBFB", &latitude_buffer) == kIOReturnSuccess && latitude_buffer) {
        acpi_device->setProperty("LatitudeI2C-SBFB", latitude_buffer);
        latitude_buffer->release();
    }
    latitude_buffer = nullptr;
    if (acpi_device->evaluateObject("SBFG", &latitude_buffer) == kIOReturnSuccess && latitude_buffer) {
        acpi_device->setProperty("LatitudeI2C-SBFG", latitude_buffer);
        latitude_buffer->release();
    }''')
s=replace_once(s,'    uint8_t const* crs = reinterpret_cast<uint8_t const*>(data->getBytesNoCopy());','''    acpi_device->setProperty("LatitudeI2C-CRSBuffer", data);
    uint8_t const* crs = reinterpret_cast<uint8_t const*>(data->getBytesNoCopy());''') if s.count('    uint8_t const* crs = reinterpret_cast<uint8_t const*>(data->getBytesNoCopy());')==1 else s
# Record return buffers separately in CRS/DSM parsing functions.
for name,key in [('parseResourcesCRS','LatitudeI2C-CRSBuffer'),('parseResourcesDSM','LatitudeI2C-DSMBuffer')]:
    start=s.index('IOReturn VoodooI2CDeviceNub::'+name)
    end=s.index('\n}',start)+2
    body=s[start:end]
    needle='    uint8_t const* crs = reinterpret_cast<uint8_t const*>(data->getBytesNoCopy());'
    if key not in body:
        body=replace_once(body,needle,'    acpi_device->setProperty("'+key+'", data);\n'+needle)
    s=s[:start]+body+s[end:]
nub.write_text(s)

controller=i2c/'VoodooI2C/VoodooI2C/VoodooI2CController/VoodooI2CControllerDriver.cpp'
s=controller.read_text()
s=replace_once(s,'    reg = readRegister(DW_IC_COMP_TYPE);','''    provider->setProperty("LatitudeI2CControllerStage", "probe-reading-component");
    reg = readRegister(DW_IC_COMP_TYPE);
    provider->setProperty("LatitudeI2CControllerType", reg, 32);''')
s=replace_once(s,'bool VoodooI2CControllerDriver::start(IOService* provider) {','''bool VoodooI2CControllerDriver::start(IOService* provider) {
    provider->setProperty("LatitudeI2CControllerStage", "start-entered");''')
s=replace_once(s,'    if (initialiseBus() != kIOReturnSuccess) {','''    if (initialiseBus() != kIOReturnSuccess) {
        provider->setProperty("LatitudeI2CControllerStage", "bus-initialization-failed");''')
s=replace_once(s,'    if (startI2CInterrupt() != kIOReturnSuccess) {','''    if (startI2CInterrupt() != kIOReturnSuccess) {
        provider->setProperty("LatitudeI2CControllerStage", "controller-interrupt-failed");''')
s=replace_once(s,'    publishNubs();','''    provider->setProperty("LatitudeI2CControllerStage", "publishing-devices");
    publishNubs();''')
controller.write_text(s)


apply(i2c, wifi)
apply_initialization(i2c, wifi)
apply_touchpad(i2c)
(out/'instrumented-DeviceNub.cpp').write_text(nub.read_text())
macsdk=subprocess.check_output(['xcrun','--sdk','macosx','--show-sdk-path'],text=True).strip()
headers=list((root/'.deps/VoodooInput').rglob('VoodooInputTransducer.h'))
assert headers
input_headers=headers[0].parent.parent
flags=['-arch','x86_64','-mmacosx-version-min=10.12','-nostdinc','-DKERNEL','-DAPPLE','-DNeXT','-D__ACIDANTHERA_MAC_SDK','-O2','-mkernel','-fno-builtin','-isysroot',macsdk,'-isystem',str(sdk/'Headers'),'-I',str(input_headers)]
objdir=out/'objects'
objdir.mkdir(exist_ok=True)
sources=list((i2c/'VoodooI2C/VoodooI2C').rglob('*.cpp'))+list((i2c/'Multitouch Support').rglob('*.cpp'))+[i2c/'Dependencies/helpers.cpp',i2c/'Dependencies/VoodooI2CACPIResourcesParser/VoodooI2CACPIResourcesParser.cpp']
objs=[]
for path in sorted(sources):
    obj=objdir/(path.relative_to(i2c).as_posix().replace('/','_').replace(' ','_')+'.o')
    print('Compiling',path,flush=True)
    subprocess.run(['xcrun','clang++','-std=gnu++17','-fno-rtti','-fno-exceptions','-fapple-kext',*flags,'-c',str(path),'-o',str(obj)],check=True)
    objs.append(str(obj))
meta=out/'kmod_info.c'
meta.write_text('''#include <mach/mach_types.h>
#include <mach/kmod.h>
extern kern_return_t _start(kmod_info_t *, void *);
extern kern_return_t _stop(kmod_info_t *, void *);
KMOD_EXPLICIT_DECL("com.alexandred.VoodooI2C", "2.9.1", _start, _stop)
__private_extern__ kmod_start_func_t *_realmain = 0;
__private_extern__ kmod_stop_func_t *_antimain = 0;
''')
mo=objdir/'kmod_info.o'
subprocess.run(['xcrun','clang',*flags,'-c',str(meta),'-o',str(mo)],check=True)
bundle=out/'VoodooI2C.kext'
binary=bundle/'Contents/MacOS/VoodooI2C'
binary.parent.mkdir(parents=True,exist_ok=True)
subprocess.run(['xcrun','clang++','-arch','x86_64','-isysroot',macsdk,'-mkernel','-fapple-kext','-static','-nostdlib','-L'+str(sdk/'Library/x86_64'),'-Xlinker','-kext','-Xlinker','-no_deduplicate',*objs,'-lkmodc++',str(mo),'-lkmod','-lcc_kext','-o',str(binary)],check=True)
info=plistlib.loads((i2c/'VoodooI2C/VoodooI2C/Info.plist').read_bytes())
info.update(CFBundleIdentifier='com.alexandred.VoodooI2C',CFBundleExecutable='VoodooI2C',CFBundleName='VoodooI2C',CFBundleVersion='2.9.1',CFBundleShortVersionString='2.9.1')
(bundle/'Contents/Info.plist').write_bytes(plistlib.dumps(info,sort_keys=False))
assert '_kmod_info' in subprocess.check_output(['nm','-gU',str(binary)],text=True)

print("Desktop touchpad resource fallback compiled; Wi-Fi binary not built or packaged.")
