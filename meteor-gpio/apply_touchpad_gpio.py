"""Opt-in Latitude I2C3 GPIO resources; preserve the working Wacom path."""
from pathlib import Path
from apply_touchpad_fixes import once


def apply(i2c):
    path = Path(i2c)/'VoodooI2C/VoodooI2C/VoodooI2CDevice/VoodooI2CDeviceNub.cpp'
    s = path.read_text()
    s = once(s, '    bool latitude_wacom_resources = false;', '''    bool latitude_touchpad_gpio = false;
    OSObject *gpio_opt = touchpad_pci ? touchpad_pci->getProperty("LatitudeTouchpadGPIO") : nullptr;
    OSData *gpio_opt_data = OSDynamicCast(OSData, gpio_opt);
    OSNumber *gpio_opt_number = OSDynamicCast(OSNumber, gpio_opt);
    bool gpio_enabled = gpio_opt == kOSBooleanTrue ||
        (gpio_opt_data && gpio_opt_data->getLength() == 1 &&
         *static_cast<const UInt8 *>(gpio_opt_data->getBytesNoCopy()) == 1) ||
        (gpio_opt_number && gpio_opt_number->unsigned64BitValue() == 1);
    if (latitude_touchpad_resources && gpio_enabled &&
        latitudeTouchpadFallbackAllowed(acpi_device, touchpad_pci)) {
        OSObject *gpio_object = nullptr;
        IOReturn status = acpi_device->evaluateObject("SBFG", &gpio_object);
        OSData *gpio = OSDynamicCast(OSData, gpio_object);
        // Exact firmware resource captured on this Latitude, not a donor pin.
        // GPIO namespace 387 -> GPP_D3 -> hardware pad 232, community 5.
        static const UInt8 expected[] = {
            0x8c,0x20,0,1,0,1,0,0x12,0,0,0,0,0,0,0x17,0,0,0x19,0,
            0x23,0,0,0,0x83,1,0x5c,0x5f,0x53,0x42,0x2e,0x47,0x50,0x49,0x30,0,0x79,0
        };
        acpi_device->setProperty("LatitudeTouchpadGPIOStatus", (UInt32)status, 32);
        if (status == kIOReturnSuccess && gpio && gpio->getLength() == sizeof(expected) &&
            memcmp(gpio->getBytesNoCopy(), expected, sizeof(expected)) == 0) {
            dsm_parser.parseACPIResources(static_cast<const UInt8 *>(gpio->getBytesNoCopy()),
                                         0, gpio->getLength());
            latitude_touchpad_gpio = dsm_parser.found_gpio_interrupts &&
                dsm_parser.gpio_interrupts.pin_number == 0x183 &&
                dsm_parser.gpio_interrupts.level_interrupt &&
                dsm_parser.gpio_interrupts.interrupt_polarity == 1;
            acpi_device->setProperty("LatitudeTouchpadGPIOBuffer", gpio);
        }
        acpi_device->setProperty("LatitudeTouchpadGPIOFallback", latitude_touchpad_gpio);
        OSSafeReleaseNULL(gpio_object);
    }
    bool latitude_wacom_resources = false;''')
    # Keep polling when GPIO is not explicitly enabled/validated, including a
    # descriptor mismatch. Leave the global polling override authoritative.
    s = once(s, '    if (force_polling) {', '''    if (latitude_touchpad_resources && !latitude_touchpad_gpio)
        force_polling = true;
    if (force_polling) {''')
    # IOInterruptEventSource may ask the trigger type before registration.
    # GPIO's interruptTypes[] has not been populated at that point. The
    # validated resource already supplies the actual level trigger.
    s = once(s, '        return gpio_controller->getInterruptType(gpio_pin, interrupt_type);', '''        if (gpio_pin == 387 && latitudeTouchpadFallbackAllowed(acpi_device,
                controller->nub->controller->physical_device.pci_device)) {
            *interrupt_type = (gpio_irq & 0x0c) ? kIOInterruptTypeLevel : kIOInterruptTypeEdge;
            return kIOReturnSuccess;
        }
        return gpio_controller->getInterruptType(gpio_pin, interrupt_type);''')
    s = once(s, '        gpio_controller->setInterruptTypeForPin(gpio_pin, gpio_irq);', '''        IOReturn configuration = gpio_controller->setInterruptTypeForPin(gpio_pin, gpio_irq);
        if (gpio_pin == 387 && latitudeTouchpadFallbackAllowed(acpi_device,
                controller->nub->controller->physical_device.pci_device)) {
            setProperty("LatitudeELANGPIORegistrationStatus", (UInt32)configuration, 32);
            if (configuration != kIOReturnSuccess)
                return configuration; // Let HID create its existing polling timer.
        }''')
    assert s.count('LatitudeTouchpadGPIOFallback') == 1
    path.write_text(s)
