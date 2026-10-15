from pathlib import Path
import shutil,subprocess,tempfile

def apply(hid,out):
    here=Path(__file__).resolve().parent
    header=here/'LatitudeELAN328E.hpp'
    # Execute the decoder on a real captured report and multi-contact fixtures.
    test=r'''
#include <cassert>
#include "LatitudeELAN328E.hpp"
int main() {
    unsigned char b[29] = {0x54,0x10,0x86,0x23,0x03,0xb8,0x08,0xde,0x05};
    LatitudeELANFrame f;
    assert(latitudeDecodeELAN(b,29,f));
    assert(f.count==1 && f.contacts[0].tip && f.contacts[0].confidence);
    assert(f.contacts[0].x==2232 && f.contacts[0].y==1502 && f.scan==0x2386);
    // Five contacts with distinct IDs, including noncontiguous/reordered IDs.
    b[1]=0x51;
    const unsigned ids[5]={8,2,15,0,6};
    for(unsigned i=0;i<5;++i) {
        b[4+5*i]=(ids[i]<<4)|3; b[5+5*i]=100+i; b[6+5*i]=0;
        b[7+5*i]=200+i; b[8+5*i]=0;
    }
    assert(latitudeDecodeELAN(b,29,f) && f.count==5 && f.button);
    for(unsigned i=0;i<5;++i) assert(f.contacts[i].id==ids[i]);
    b[4]&=~1; assert(latitudeDecodeELAN(b,29,f) && !f.contacts[0].confidence);
    b[4]&=~2; assert(latitudeDecodeELAN(b,29,f) && !f.contacts[0].tip);
    b[1]=0; assert(latitudeDecodeELAN(b,29,f) && f.count==0 && !f.button);
    b[1]=0x60; assert(!latitudeDecodeELAN(b,29,f));
    b[1]=0x20; b[4]=3; b[9]=3; assert(!latitudeDecodeELAN(b,29,f));
    b[1]=0x10; b[5]=0xff; b[6]=0xff; assert(!latitudeDecodeELAN(b,29,f));
    b[0]=1; assert(!latitudeDecodeELAN(b,29,f));
    assert(!latitudeDecodeELAN(b,28,f));
    assert(!latitudeDecodeELAN(nullptr,29,f));
    assert(latitudeELANShouldRecover(true,true,35,true,1024,0));
    assert(!latitudeELANShouldRecover(true,true,0,true,1024,0));
    assert(!latitudeELANShouldRecover(true,true,35,false,1024,0));
    assert(!latitudeELANShouldRecover(true,true,35,true,1023,0));
    assert(!latitudeELANShouldRecover(true,true,35,true,1024,3));
    assert(!latitudeELANShouldRecover(false,true,35,true,1024,0));
    assert(!latitudeELANShouldRecover(true,false,35,true,1024,0));
}
'''
    with tempfile.TemporaryDirectory() as folder:
        folder=Path(folder);(folder/'test.cpp').write_text(test)
        exe=folder/'test'
        subprocess.run(['clang++','-std=c++17','-I'+str(here),str(folder/'test.cpp'),'-o',str(exe)],check=True)
        subprocess.run([str(exe)],check=True)
    print('Custom ELAN decoder: captured report, five contacts, reordered IDs, palm, lift, release and malformed packet cases passed.')
    shutil.copy2(header,hid/'VoodooI2CHID/LatitudeELAN328E.hpp')
    p=hid/'VoodooI2CHID/VoodooI2CPrecisionTouchpadHIDEventDriver.cpp'
    s=p.read_text().replace('#define super VoodooI2CMultitouchHIDEventDriver',
        '#include "LatitudeELAN328E.hpp"\n#define super VoodooI2CMultitouchHIDEventDriver')
    needle='    super::handleInterruptReport(timestamp, report, report_type, report_id);'
    assert s.count(needle)==1
    s=s.replace(needle,'''    if (getVendorID() == 0x04f3 && getProductID() == 0x328e) {
        if (!awake || report_type != kIOHIDReportTypeInput)
            return;
        UInt8 bytes[29];
        LatitudeELANFrame frame;
        if (!report || report->getLength() != sizeof(bytes) ||
            report->readBytes(0, bytes, sizeof(bytes)) != sizeof(bytes) ||
            !latitudeDecodeELAN(bytes, sizeof(bytes), frame)) {
            setProperty("LatitudeELANCustomRejected", ++latitude_rejected, 64);
            return;
        }
        if (!digitiser.transducers || digitiser.transducers->getCount() != 5)
            return;
        // Replace only this ELAN's generic HID-element assembly. Every frame
        // explicitly refreshes the slots; zero contacts emits a release frame.
        for (unsigned i = 0; i < 5; ++i) {
            VoodooI2CDigitiserTransducer *t = OSDynamicCast(VoodooI2CDigitiserTransducer,
                digitiser.transducers->getObject(i));
            if (!t) return;
            const LatitudeELANContact &c = frame.contacts[i];
            bool present = i < frame.count;
            t->id = 0x54; t->secondary_id = c.id; t->timestamp = timestamp;
            t->type = kDigitiserTransducerFinger;
            t->is_valid = present; t->in_range = present && c.tip;
            t->has_secondary_button = false;
            t->tip_switch.update(present && c.tip, timestamp);
            t->confidence.update(present && c.confidence, timestamp);
            t->physical_button.update(i == 0 && frame.button, timestamp);
            if (present) {
                t->coordinates.x.update(c.x, timestamp);
                t->coordinates.y.update(c.y, timestamp);
            }
        }
        VoodooI2CMultitouchEvent event;
        event.contact_count = frame.count;
        event.transducers = digitiser.transducers;
        forwardReport(event, timestamp);
        setProperty("LatitudeELANCustomFrames", ++latitude_frames, 64);
        setProperty("LatitudeELANCustomContacts", frame.count, 32);
        setProperty("LatitudeELANCustomScanTime", frame.scan, 32);
        return;
    }
'''+needle)
    p.write_text(s)
    p=hid/'VoodooI2CHID/VoodooI2CPrecisionTouchpadHIDEventDriver.hpp'
    s=p.read_text();assert s.count('    bool ready = false;')==1
    p.write_text(s.replace('    bool ready = false;',
        '    bool ready = false;\n    UInt64 latitude_frames = 0;\n    UInt64 latitude_rejected = 0;'))
    p=hid/'VoodooI2CHID/VoodooI2CHIDDevice.hpp'
    s=p.read_text();assert s.count('    UInt64 latitude_input_errors = 0;')==1
    p.write_text(s.replace('    UInt64 latitude_input_errors = 0;',
        '    UInt64 latitude_input_errors = 0;\n    UInt64 latitude_reads = 0;\n    UInt64 latitude_resets = 0;\n    UInt64 latitude_invalid = 0;'))
    p=hid/'VoodooI2CHID/VoodooI2CHIDDevice.cpp';s=p.read_text()
    needle='    int return_size = report[0] | report[1] << 8;'
    assert s.count(needle)==1
    s=s.replace(needle,needle+'''
    if (latitude_elan) {
        ++latitude_reads;
        if (return_size == 0) ++latitude_resets;
        if (return_size > hid_descriptor.wMaxInputLength || return_size == 1)
            ++latitude_invalid;
        if (latitude_reads <= 16 || !(latitude_reads & 0x7f)) {
            setProperty("LatitudeELANReadAttempts", latitude_reads, 64);
            setProperty("LatitudeELANResetPackets", latitude_resets, 64);
            setProperty("LatitudeELANInvalidPackets", latitude_invalid, 64);
            setProperty("LatitudeELANInputCount", latitude_input_count, 64);
            setProperty("LatitudeELANLastReadBytes", report, hid_descriptor.wMaxInputLength);
        }
    }
''')
    p.write_text(s)
    (out/'custom-ELAN-decoder.hpp').write_bytes(header.read_bytes())
    p=hid/'VoodooI2CHID/VoodooI2CHIDDevice.hpp'
    s=p.read_text().replace('    UInt64 latitude_reads = 0;', '''    UInt64 latitude_reads = 0;
    UInt64 latitude_ptp_idle_reads = 0;
    UInt32 latitude_recoveries = 0;
    UInt64 latitude_ptp_frames = 0;
    bool latitude_legacy_seen = false;''')
    p.write_text(s)
    p=hid/'VoodooI2CHID/VoodooI2CHIDDevice.cpp';s=p.read_text()
    s=s.replace('#include "VoodooI2CHIDDevice.hpp"', '#include "VoodooI2CHIDDevice.hpp"\n#include "LatitudeELAN328E.hpp"')
    needle='''    if (latitude_elan) {
        ++latitude_reads;'''
    assert s.count(needle)==1
    s=s.replace(needle,'''    if (latitude_elan) {
        if (ready_for_input) {
            if (return_size == 31 && report[2] == 0x54) {
                ++latitude_ptp_frames;
                latitude_ptp_idle_reads = 0;
                latitude_legacy_seen = false;
            } else {
                ++latitude_ptp_idle_reads;
                if (return_size >= 3 && return_size <= hid_descriptor.wMaxInputLength && report[2] == 1)
                    latitude_legacy_seen = true;
            }
        }
        ++latitude_reads;''')
    needle='''        if (awake)
            VoodooI2CHIDDevice::getInputReport();
        if (interrupt_simulator)
            interrupt_simulator->setTimeoutMS(4);'''
    assert s.count(needle)==1
    s=s.replace(needle,'''        if (awake)
            VoodooI2CHIDDevice::getInputReport();
        // Recover only after real PTP traffic, a legacy mouse packet and a
        // long drought of PTP frames. At most three attempts per load, with
        // at least 1024 polling intervals between attempts. No hardware reset.
        if (latitudeELANShouldRecover(awake, ready_for_input, latitude_ptp_frames,
                latitude_legacy_seen, latitude_ptp_idle_reads, latitude_recoveries)) {
            ++latitude_recoveries;
            latitude_ptp_idle_reads = 0;
            setProperty("LatitudeELANModeRecoveryAttempts", latitude_recoveries, 32);
            IOBufferMemoryDescriptor *mode = IOBufferMemoryDescriptor::inTaskWithOptions(kernel_task, 0, 3);
            if (mode) {
                const UInt8 enable[] = {0x03,0x03,0x00};
                mode->writeBytes(0, enable, 3);
                // Direct transport GET_REPORT here avoids IOHID element locks
                // and startup matching. Record hardware bytes, not cached mode.
                IOReturn status = getReport(mode, kIOHIDReportTypeFeature, 3);
                UInt8 actual[3] = {};
                mode->readBytes(0, actual, 3);
                if (status != kIOReturnSuccess) bzero(actual, 3);
                setProperty("LatitudeELANModeBeforeStatus", (UInt32)status, 32);
                setProperty("LatitudeELANModeBeforeBytes", actual, 3);
                mode->writeBytes(0, enable, 3);
                status = setReport(mode, kIOHIDReportTypeFeature, 3);
                setProperty("LatitudeELANModeWriteStatus", (UInt32)status, 32);
                const UInt8 surface[] = {0x05,0x03,0x00};
                mode->writeBytes(0, surface, 3);
                status = setReport(mode, kIOHIDReportTypeFeature, 5);
                setProperty("LatitudeELANSurfaceRecoveryStatus", (UInt32)status, 32);
                mode->writeBytes(0, enable, 3);
                status = getReport(mode, kIOHIDReportTypeFeature, 3);
                mode->readBytes(0, actual, 3);
                if (status != kIOReturnSuccess) bzero(actual, 3);
                setProperty("LatitudeELANModeAfterStatus", (UInt32)status, 32);
                setProperty("LatitudeELANModeAfterBytes", actual, 3);
                mode->release();
            }
        }
        if (interrupt_simulator)
            interrupt_simulator->setTimeoutMS(4);''')
    p.write_text(s)
