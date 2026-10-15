"""Pinned HID build: null-safe framebuffer transform and bounded ELAN reports."""
from pathlib import Path
import plistlib, re, subprocess
root = Path.cwd()
hid = root/'.deps/VoodooI2CHID'
i2c = root/'.deps/VoodooI2C'
sdk = root/'.deps/MacKernelSDK'
out = root/'ci-diagnostics'

def once(s, a, b):
    assert s.count(a) == 1, (a[:80], s.count(a))
    return s.replace(a, b)

p = hid/'VoodooI2CHID/VoodooI2CTouchscreenHIDEventDriver.cpp'
s = p.read_text()
s = once(s, '        current_rotation = number->unsigned8BitValue() / 0x10;',
'''        // A framebuffer may exist before it publishes IOFBTransform.
        // Panic 2026-10-15: forwardReport+0x4f dereferences this null OSNumber.
        current_rotation = number ? number->unsigned8BitValue() / 0x10 : 0;''')
s = once(s, '        multitouch_interface->setProperty(kIOFBTransformKey, current_rotation, 8);',
'''        if (multitouch_interface)
            multitouch_interface->setProperty(kIOFBTransformKey, current_rotation, 8);''')
p.write_text(s)
p = hid/'VoodooI2CHID/VoodooI2CHIDDevice.hpp'
p.write_text(once(p.read_text(), '    bool awake;', '''    bool awake;
    UInt64 latitude_input_count = 0;
    UInt64 latitude_input_errors = 0;'''))
p = hid/'VoodooI2CHID/VoodooI2CHIDDevice.cpp'
s = p.read_text()
s = once(s, '''    unsigned char* report = (unsigned char *)IOMalloc(hid_descriptor.wMaxInputLength);

    api->readI2C(report, hid_descriptor.wMaxInputLength);

    int return_size = report[0] | report[1] << 8;''', '''    bool latitude_elan = hid_descriptor.wVendorID == 0x04f3 && hid_descriptor.wProductID == 0x328e;
    if (hid_descriptor.wMaxInputLength < 2)
        return;
    unsigned char* report = (unsigned char *)IOMalloc(hid_descriptor.wMaxInputLength);
    if (!report)
        return;
    bzero(report, hid_descriptor.wMaxInputLength);
    ret = api->readI2C(report, hid_descriptor.wMaxInputLength);
    if (ret != kIOReturnSuccess) {
        if (latitude_elan) {
            setProperty("LatitudeELANInputReadStatus", (UInt32)ret, 32);
            setProperty("LatitudeELANInputErrors", ++latitude_input_errors, 64);
        }
        IOFree(report, hid_descriptor.wMaxInputLength);
        return;
    }
    int return_size = report[0] | report[1] << 8;''')
s = once(s, '    if (return_size > hid_descriptor.wMaxInputLength) {',
'''    if (return_size < 2 || return_size > hid_descriptor.wMaxInputLength) {''')
s = once(s, '''    buffer = IOBufferMemoryDescriptor::inTaskWithOptions(kernel_task, 0, return_size);
    buffer->writeBytes(0, report + 2, return_size - 2);''', '''    if (return_size == 2)
        goto exit;
    // The two-byte HID-over-I2C length prefix is not part of the HID payload.
    // Scope the corrected descriptor length to the report-confirmed ELAN device.
    buffer = IOBufferMemoryDescriptor::inTaskWithOptions(kernel_task, 0,
        latitude_elan ? return_size - 2 : return_size);
    if (!buffer)
        goto exit;
    buffer->writeBytes(0, report + 2, return_size - 2);
    if (latitude_elan) {
        ++latitude_input_count;
        if (latitude_input_count <= 16 || (latitude_input_count & 0xff) == 0) {
            setProperty("LatitudeELANInputCount", latitude_input_count, 64);
            setProperty("LatitudeELANInputReadStatus", (UInt32)ret, 32);
            setProperty("LatitudeELANLastInput", report, return_size);
        }
    }''')
s = once(s, '''void VoodooI2CHIDDevice::simulateInterrupt(OSObject* owner, IOTimerEventSource* timer) {
    AbsoluteTime prev_time = last_multi_touch_event;''', '''void VoodooI2CHIDDevice::simulateInterrupt(OSObject* owner, IOTimerEventSource* timer) {
    // ELAN hybrid reports must not depend on another digitizer's global timestamp
    // or alternate between 2 ms busy and 50 ms idle polling. Yield after each read.
    if (hid_descriptor.wVendorID == 0x04f3 && hid_descriptor.wProductID == 0x328e) {
        if (!getProperty("LatitudeELANPollingIntervalMS"))
            setProperty("LatitudeELANPollingIntervalMS", 4, 32);
        if (awake)
            VoodooI2CHIDDevice::getInputReport();
        if (interrupt_simulator)
            interrupt_simulator->setTimeoutMS(4);
        return;
    }
    AbsoluteTime prev_time = last_multi_touch_event;''')
p.write_text(s)
p = hid/'VoodooI2CHID/VoodooI2CPrecisionTouchpadHIDEventDriver.cpp'
s = p.read_text()
s = once(s, '    ready = true;', '''    // Do not issue synchronous GET_REPORT from inside handleStart.
    // Keep upstream mode switching and expose the cached mode, without extra bus I/O.
    setProperty("LatitudePrecisionModeValue", digitiser.input_mode->getValue(), 32);
    setProperty("LatitudePrecisionSynchronousReadback", false);
    // Captured ELAN 04f3:328e descriptor: report 5 has Surface Switch (0x57)
    // and Button Switch (0x58) at bits 0/1, followed by 14 constant bits.
    // Match Linux TOUCHPAD_REPORT_ALL without issuing a blocking GET_REPORT.
    if (getVendorID() == 0x04f3 && getProductID() == 0x328e && hid_device) {
        const UInt8 enable_surface[] = { 0x05, 0x03, 0x00 };
        IOBufferMemoryDescriptor *feature = IOBufferMemoryDescriptor::inTaskWithOptions(
            kernel_task, 0, sizeof(enable_surface));
        IOReturn status = kIOReturnNoMemory;
        if (feature) {
            feature->writeBytes(0, enable_surface, sizeof(enable_surface));
            status = hid_device->setReport(feature, kIOHIDReportTypeFeature, 0x05);
            feature->release();
        }
        setProperty("LatitudeELANSurfaceEnableStatus", (UInt32)status, 32);
    }
    ready = true;''')
s = once(s, '    super::handleInterruptReport(timestamp, report, report_type, report_id);', '''    super::handleInterruptReport(timestamp, report, report_type, report_id);
    // Record multi-finger delivery after HID parsing; do not capture keyboard input.
    if (hid_device && getVendorID() == 0x04f3 &&
        getProductID() == 0x328e && digitiser.contact_count) {
        UInt32 count = digitiser.contact_count->getValue();
        setProperty("LatitudeELANContactCount", count, 32);
        OSNumber *previous = OSDynamicCast(OSNumber, getProperty("LatitudeELANMaxContacts"));
        if (!previous || count > previous->unsigned32BitValue())
            setProperty("LatitudeELANMaxContacts", count, 32);
    }''')
p.write_text(s)
# Standalone checkout: resolve the original monorepo-relative header references.
from apply_custom_elan import apply as apply_custom_elan
apply_custom_elan(hid, out)
for p in (hid/'VoodooI2CHID').rglob('*'):
    if p.suffix not in ('.cpp', '.hpp'): continue
    s = p.read_text()
    s = re.sub(r'#include "(?:\.\./){3,}([^"]+)"',
               lambda m: '#include "'+Path(m.group(1)).name+'"', s)
    p.write_text(s)

macsdk = subprocess.check_output(['xcrun','--sdk','macosx','--show-sdk-path'], text=True).strip()
headers = {p.parent for base in [i2c, hid, root/'.deps/VoodooInput'] for p in base.rglob('*.hpp')}
headers |= {p.parent for p in (root/'.deps/VoodooInput').rglob('*.h')}
flags = ['-arch','x86_64','-mmacosx-version-min=10.12','-nostdinc','-DKERNEL','-DAPPLE','-DNeXT',
         '-D__ACIDANTHERA_MAC_SDK','-O2','-mkernel','-fno-builtin','-isysroot',macsdk,
         '-isystem',str(sdk/'Headers')]+['-I'+str(p) for p in sorted(headers)]
objdir = out/'hid-objects'; objdir.mkdir(exist_ok=True)
objs = []
for source in sorted((hid/'VoodooI2CHID').rglob('*.cpp')):
    obj = objdir/(source.relative_to(hid).as_posix().replace('/','_')+'.o')
    subprocess.run(['xcrun','clang++','-std=gnu++17','-fno-rtti','-fno-exceptions','-fapple-kext',
                    *flags,'-c',str(source),'-o',str(obj)], check=True)
    objs.append(str(obj))
meta = objdir/'meta.c'
meta.write_text('''#include <mach/mach_types.h>
#include <mach/kmod.h>
extern kern_return_t _start(kmod_info_t *, void *);
extern kern_return_t _stop(kmod_info_t *, void *);
KMOD_EXPLICIT_DECL("com.alexandred.VoodooI2CHID", "1.0", _start, _stop)
__private_extern__ kmod_start_func_t *_realmain = 0;
__private_extern__ kmod_stop_func_t *_antimain = 0;
''')
subprocess.run(['xcrun','clang',*flags,'-c',str(meta),'-o',str(objdir/'meta.o')], check=True)
binary = out/'VoodooI2CHID.kext/Contents/MacOS/VoodooI2CHID'
binary.parent.mkdir(parents=True, exist_ok=True)
subprocess.run(['xcrun','clang++','-arch','x86_64','-isysroot',macsdk,'-mkernel','-fapple-kext',
                '-static','-nostdlib','-L'+str(sdk/'Library/x86_64'),'-Xlinker','-kext','-Xlinker',
                '-no_deduplicate',*objs,'-lkmodc++',str(objdir/'meta.o'),'-lkmod','-lcc_kext',
                '-o',str(binary)], check=True)
text = (hid/'VoodooI2CHID/Info.plist').read_text().replace('$(EXECUTABLE_NAME)','VoodooI2CHID').replace(
    '$(PRODUCT_BUNDLE_IDENTIFIER)','com.alexandred.VoodooI2CHID').replace('$(PRODUCT_NAME)','VoodooI2CHID')
info = plistlib.loads(text.encode())
(binary.parents[1]/'Info.plist').write_bytes(plistlib.dumps(info, sort_keys=False))
assert '_kmod_info' in subprocess.check_output(['nm','-gU',str(binary)], text=True)
for marker in [b'LatitudeELANInputCount',b'LatitudeELANMaxContacts',b'LatitudePrecisionSynchronousReadback',b'LatitudeELANSurfaceEnableStatus',b'LatitudeELANPollingIntervalMS']:
    assert marker in binary.read_bytes()
for p in (hid/'VoodooI2CHID').glob('*.cpp'):
    (objdir/p.name).write_bytes(p.read_bytes())
print('Pinned HID stability build passed; GPIO mapping remains unchanged.')
