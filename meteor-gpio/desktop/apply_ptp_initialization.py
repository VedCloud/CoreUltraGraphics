"""Exact-device, one-time deferred PTP feature initialization based on Linux."""
def apply(hid):
    p=hid/'VoodooI2CHID/VoodooI2CHIDDevice.hpp';s=p.read_text()
    needle='    UInt64 latitude_reads = 0;';assert s.count(needle)==1
    s=s.replace(needle,needle+'''
    bool latitude_ptp_initialized = false;
    IOReturn latitudeELANFeature(UInt8 id, UInt16 length, UInt8 *destination);''')
    p.write_text(s)
    p=hid/'VoodooI2CHID/VoodooI2CHIDDevice.cpp';s=p.read_text()
    needle='void VoodooI2CHIDDevice::simulateInterrupt(OSObject* owner, IOTimerEventSource* timer) {'
    assert s.count(needle)==1
    s=s.replace(needle,'''IOReturn VoodooI2CHIDDevice::latitudeELANFeature(UInt8 id, UInt16 length, UInt8 *destination) {
    if (!destination || !length || length > 257) return kIOReturnBadArgument;
    UInt8 command[6];
    if (!latitudeELANFeatureCommand(command, hid_descriptor.wCommandRegister,
            hid_descriptor.wDataRegister, id)) return kIOReturnBadArgument;
    UInt8 *reply = static_cast<UInt8*>(IOMalloc(length+2));
    if (!reply) return kIOReturnNoMemory;
    bzero(reply,length+2); bzero(destination,length);
    IOReturn status = api->writeReadI2C(command,sizeof(command),reply,length+2);
    if (status == kIOReturnSuccess) {
        if (latitudeELANFeatureReply(reply,length+2,id,length))
            memcpy(destination,reply+2,length);
        else status = kIOReturnUnderrun;
    }
    IOFree(reply,length+2);
    return status;
}

'''+needle)
    needle='''        if (!getProperty("LatitudeELANTransportBuild"))
            setProperty("LatitudeELANTransportBuild", "test16-explicit-input");'''
    assert s.count(needle)==1
    s=s.replace(needle,'''        if (!getProperty("LatitudeELANTransportBuild"))
            setProperty("LatitudeELANTransportBuild", "test19-PTP-feature-init");
        if (awake && ready_for_input && !latitude_ptp_initialized) {
            // Never run these requests from HID matching/handleStart. Execute
            // once on the existing timer after startup has completed.
            latitude_ptp_initialized = true;
            // Test16's repeated probes/writes did not help. This test isolates
            // the Linux PTP setup sequence, followed by plain 4ms raw polling.
            latitude_explicit_failures = 3;
            latitude_explicit_active = false;
            latitude_recoveries = 3;
            // Read firmware decisions rather than infer them from attachment.
            const char *names[] = {"\\\\OSYS","\\\\TPDM","\\\\PS2D","HID2"};
            const char *keys[] = {"LatitudeELANFirmwareOSYS","LatitudeELANFirmwareTPDM",
                "LatitudeELANFirmwarePS2D","LatitudeELANFirmwareHIDRegister"};
            const char *statusKeys[] = {"LatitudeELANFirmwareOSYSStatus","LatitudeELANFirmwareTPDMStatus",
                "LatitudeELANFirmwarePS2DStatus","LatitudeELANFirmwareHIDRegisterStatus"};
            for (unsigned i=0;i<4;++i) {
                OSObject *object = nullptr;
                IOReturn firmwareStatus = acpi_device->evaluateObject(names[i],&object);
                setProperty(statusKeys[i],(UInt32)firmwareStatus,32);
                OSNumber *number = OSDynamicCast(OSNumber,object);
                if (firmwareStatus == kIOReturnSuccess && number)
                    setProperty(keys[i],number->unsigned32BitValue(),32);
                OSSafeReleaseNULL(object);
            }
            OSObject *resources = nullptr;
            IOReturn resourceStatus = acpi_device->evaluateObject("_CRS",&resources);
            setProperty("LatitudeELANFirmwareCRSStatus",(UInt32)resourceStatus,32);
            OSData *resourceData = OSDynamicCast(OSData,resources);
            if (resourceStatus == kIOReturnSuccess && resourceData)
                setProperty("LatitudeELANFirmwareCRSBytes",resourceData);
            OSSafeReleaseNULL(resources);
            UInt8 caps[2] = {}, blob[257] = {}, vendor[5] = {}, mode[3] = {};
            IOReturn status = latitudeELANFeature(2,sizeof(caps),caps);
            setProperty("LatitudeELANCapabilitiesStatus", (UInt32)status,32);
            if (status == kIOReturnSuccess) setProperty("LatitudeELANCapabilitiesBytes",caps,sizeof(caps));
            status = latitudeELANFeature(6,sizeof(blob),blob);
            setProperty("LatitudeELANCertificationStatus", (UInt32)status,32);
            setProperty("LatitudeELANCertificationValid",status == kIOReturnSuccess);
            // Report13 also advertises FF00:C5 at usage_index0. Linux fetches
            // such feature reports, not just the 256-byte certification report.
            status = latitudeELANFeature(13,sizeof(vendor),vendor);
            setProperty("LatitudeELANVendorFeatureStatus", (UInt32)status,32);
            IOBufferMemoryDescriptor *feature = IOBufferMemoryDescriptor::inTaskWithOptions(kernel_task,0,3);
            if (feature) {
                const UInt8 normal[] = {7,0,0}, precision[] = {3,3,0}, surface[] = {5,3,0};
                feature->writeBytes(0,normal,3);
                status = setReport(feature,kIOHIDReportTypeFeature,7);
                setProperty("LatitudeELANNormalLatencyWriteStatus",(UInt32)status,32);
                feature->writeBytes(0,precision,3);
                status = setReport(feature,kIOHIDReportTypeFeature,3);
                setProperty("LatitudeELANPTPInitModeStatus",(UInt32)status,32);
                feature->writeBytes(0,surface,3);
                status = setReport(feature,kIOHIDReportTypeFeature,5);
                setProperty("LatitudeELANPTPInitSurfaceStatus",(UInt32)status,32);
                feature->release();
            } else setProperty("LatitudeELANPTPInitAllocationStatus",(UInt32)kIOReturnNoMemory,32);
            status = latitudeELANFeature(7,sizeof(mode),mode);
            setProperty("LatitudeELANLatencyReadbackStatus",(UInt32)status,32);
            if (status == kIOReturnSuccess) setProperty("LatitudeELANLatencyBytes",mode,sizeof(mode));
            status = latitudeELANFeature(3,sizeof(mode),mode);
            setProperty("LatitudeELANPTPInitReadbackStatus",(UInt32)status,32);
            if (status == kIOReturnSuccess) setProperty("LatitudeELANPTPInitModeBytes",mode,sizeof(mode));
            setProperty("LatitudeELANPTPInitializationAttempted",true);
        }''')
    p.write_text(s)
