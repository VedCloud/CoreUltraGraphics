from pathlib import Path

def apply(hid):
    p=hid/'VoodooI2CHID/VoodooI2CHIDDevice.hpp';s=p.read_text()
    assert s.count('    UInt64 latitude_reads = 0;')==1
    s=s.replace('    UInt64 latitude_reads = 0;', '''    UInt64 latitude_reads = 0;
    IOService *latitude_gpio_sample_service = nullptr;
    UInt64 latitude_gpio_checks = 0;
    UInt64 latitude_gpio_low = 0;
    UInt64 latitude_gpio_skipped = 0;
    UInt64 latitude_gpio_reads = 0;''')
    p.write_text(s)
    p=hid/'VoodooI2CHID/VoodooI2CHIDDevice.cpp';s=p.read_text()
    needle='void VoodooI2CHIDDevice::releaseResources() {'
    assert s.count(needle)==1
    s=s.replace(needle,needle+'\n    OSSafeReleaseNULL(latitude_gpio_sample_service);')
    needle='''        if (!getProperty("LatitudeELANTransportBuild"))
            setProperty("LatitudeELANTransportBuild", "test16-explicit-input");'''
    assert s.count(needle)==1
    s=s.replace(needle,'''        if (!getProperty("LatitudeELANTransportBuild"))
            setProperty("LatitudeELANTransportBuild", "test17-passive-ready");
        // Leave reset/startup handshakes on the established path. Once ready,
        // sample the physical data-ready line in this existing HID timer.
        // Unlike the withdrawn GPIO watchdog this never dispatches a callback.
        if (awake && ready_for_input) {
            if (!latitude_gpio_sample_service && !(latitude_gpio_checks & 255)) {
                OSDictionary *match = IOService::serviceMatching("VoodooGPIOMeteorLakeP");
                OSIterator *services = match ? IOService::getMatchingServices(match) : nullptr;
                OSSafeReleaseNULL(match);
                if (services) {
                    latitude_gpio_sample_service = OSDynamicCast(IOService, services->getNextObject());
                    if (latitude_gpio_sample_service) latitude_gpio_sample_service->retain();
                    services->release();
                }
            }
            UInt32 pad = 0;
            IOReturn status = latitude_gpio_sample_service ?
                latitude_gpio_sample_service->callPlatformFunction("LatitudeELANReadPad232", false,
                    &pad, nullptr, nullptr, nullptr) : kIOReturnNotFound;
            ++latitude_gpio_checks;
            if (status == kIOReturnSuccess) {
                if (!(pad & 2)) {
                    ++latitude_gpio_low;
                    // This path uses only raw input reads while data-ready is
                    // asserted: no explicit GET_REPORT or mode recovery writes.
                    latitude_explicit_failures = 3;
                    latitude_explicit_active = false;
                    VoodooI2CHIDDevice::getInputReport();
                    ++latitude_gpio_reads;
                } else {
                    ++latitude_gpio_skipped;
                }
            }
            if (latitude_gpio_checks <= 16 || !(latitude_gpio_checks & 127) || status != kIOReturnSuccess) {
                setProperty("LatitudeELANReadyStatus", (UInt32)status, 32);
                setProperty("LatitudeELANReadyPad", pad, 32);
                setProperty("LatitudeELANReadyChecks", latitude_gpio_checks, 64);
                setProperty("LatitudeELANReadyLow", latitude_gpio_low, 64);
                setProperty("LatitudeELANReadySkipped", latitude_gpio_skipped, 64);
                setProperty("LatitudeELANReadyReads", latitude_gpio_reads, 64);
            }
            if (status == kIOReturnSuccess) {
                if (interrupt_simulator) interrupt_simulator->setTimeoutMS(4);
                return;
            }
        }''')
    p.write_text(s)
