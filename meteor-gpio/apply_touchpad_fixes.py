"""Opt-in resource fallback for the report-verified Latitude ELAN touchpad.

Apply after the existing report/initialization patches. No ACPI rewriting,
guessed HID register, interrupt pin, or change to the existing Wacom path.
"""
from pathlib import Path


def once(text, old, new):
    assert text.count(old) == 1, (old[:90], text.count(old))
    return text.replace(old, new)


def apply(i2c):
    path = Path(i2c)/'VoodooI2C/VoodooI2C/VoodooI2CDevice/VoodooI2CDeviceNub.cpp'
    s = path.read_text()
    anchor = 'static bool latitudeWacomFallbackAllowed('
    helper = '''static bool latitudeTouchpadFallbackAllowed(IOACPIPlatformDevice *acpi, IOPCIDevice *pci) {
    if (!acpi || !pci ||
        pci->configRead16(kIOPCIConfigVendorID) != 0x8086 ||
        pci->configRead16(kIOPCIConfigDeviceID) != 0x7e7b) return false;
    OSObject *opt = pci->getProperty("LatitudeTouchpadResourceFallback");
    OSData *data = OSDynamicCast(OSData, opt);
    OSNumber *number = OSDynamicCast(OSNumber, opt);
    bool enabled = opt == kOSBooleanTrue ||
        (data && data->getLength() == 1 &&
         *static_cast<const UInt8 *>(data->getBytesNoCopy()) == 1) ||
        (number && number->unsigned64BitValue() == 1);
    OSData *name = OSDynamicCast(OSData, acpi->getProperty("name"));
    return enabled && name && name->getLength() == 9 &&
        memcmp(name->getBytesNoCopy(), "VEN_04F3", 9) == 0;
}

'''
    s = once(s, anchor, helper + anchor)
    s = once(s, '    params[0]->release();', '''    // HID2 is initialized by Dell firmware. Do not substitute a donor value.
    if (ret != kIOReturnSuccess && latitudeTouchpadFallbackAllowed(acpi_device, latitude_pci) &&
        strcmp(uuid, I2C_DSM_HIDG) == 0) {
        OSSafeReleaseNULL(*result);
        if (index == DSM_SUPPORT_INDEX) {
            UInt8 functions = 0x03;
            *result = OSData::withBytes(&functions, sizeof(functions));
            ret = *result ? kIOReturnSuccess : kIOReturnNoMemory;
        } else if (index == HIDG_DESC_INDEX) {
            ret = acpi_device->evaluateObject("HID2", result);
            OSNumber *address = OSDynamicCast(OSNumber, *result);
            acpi_device->setProperty("LatitudeTouchpadHIDStatus", (UInt32)ret, 32);
            if (ret == kIOReturnSuccess && address && address->unsigned64BitValue() > 0 &&
                address->unsigned64BitValue() <= 0xffff) {
                acpi_device->setProperty("LatitudeTouchpadHIDRegister", address);
                acpi_device->setProperty("LatitudeTouchpadHIDFallback", true);
            } else {
                OSSafeReleaseNULL(*result);
                ret = kIOReturnNotFound;
            }
        }
    }
    params[0]->release();''')
    s = once(s, '    bool latitude_wacom_resources = false;', '''    bool latitude_touchpad_resources = false;
    IOPCIDevice *touchpad_pci = controller->nub->controller->physical_device.pci_device;
    if (!crs_parser.found_i2c && !dsm_parser.found_i2c &&
        latitudeTouchpadFallbackAllowed(acpi_device, touchpad_pci)) {
        OSObject *serial_object = nullptr;
        IOReturn status = acpi_device->evaluateObject("SBFB", &serial_object);
        OSData *serial = OSDynamicCast(OSData, serial_object);
        acpi_device->setProperty("LatitudeTouchpadResourceStatus", (UInt32)status, 32);
        // Exact descriptor shape/path/address captured on this laptop in Linux
        // and macOS. No GPIO resource is parsed: this trial uses polling.
        if (status == kIOReturnSuccess && serial && serial->getLength() == 35) {
            const UInt8 *a = static_cast<const UInt8 *>(serial->getBytesNoCopy());
            UInt32 speed = static_cast<UInt32>(a[12]) | (static_cast<UInt32>(a[13]) << 8) |
                (static_cast<UInt32>(a[14]) << 16) | (static_cast<UInt32>(a[15]) << 24);
            if (a[0] == 0x8e && a[1] == 0x1e && a[2] == 0 && a[5] == 1 &&
                a[16] == 0x2c && a[17] == 0 && speed > 0 && speed <= 1000000 &&
                memcmp(a + 18, "\\\\_SB.PC00.I2C3", 15) == 0 &&
                a[33] == 0x79 && a[34] == 0) {
                dsm_parser.parseACPIResources(a, 0, serial->getLength());
                latitude_touchpad_resources = dsm_parser.found_i2c;
                acpi_device->setProperty("LatitudeTouchpadResourceBuffer", serial);
            }
        }
        acpi_device->setProperty("LatitudeTouchpadResourceFallback", latitude_touchpad_resources);
        OSSafeReleaseNULL(serial_object);
    }
    bool latitude_wacom_resources = false;''')
    s = once(s,
        '    if (!latitude_wacom_resources && validateAPICInterrupt() == kIOReturnSuccess)',
        '    if (!latitude_wacom_resources && !latitude_touchpad_resources && validateAPICInterrupt() == kIOReturnSuccess)')
    # Existing per-controller polling property is evaluated after this point.
    assert '"LatitudeTouchpadResourceFallback"' in s
    assert s.count('static bool latitudeWacomFallbackAllowed(') == 1
    assert s.count('static bool latitudeTouchpadFallbackAllowed(') == 1
    path.write_text(s)
