"""Port bounded Linux post-STOP idle handling to opt-in Intel 7E7B only."""
from pathlib import Path
import shutil, subprocess

def once(s,a,b):
    assert s.count(a)==1,(a[:100],s.count(a))
    return s.replace(a,b)

def apply(i2c,out):
    here=Path(__file__).resolve().parent
    subprocess.run(['xcrun','clang++','-std=c++17',str(here/'test_i2c_completion.cpp'),
                    '-o',str(out/'test-i2c-completion')],check=True)
    subprocess.run([str(out/'test-i2c-completion')],check=True)
    folder=i2c/'VoodooI2C/VoodooI2C/VoodooI2CController'
    shutil.copy2(here/'LatitudeI2CCompletion.hpp',folder/'LatitudeI2CCompletion.hpp')
    p=folder/'VoodooI2CControllerDriver.cpp';s=p.read_text()
    s='#include "LatitudeI2CCompletion.hpp"\n'+s
    s=once(s,'    requestTransferI2C();','''    IOPCIDevice *latitudePCI = nub->controller->physical_device.pci_device;
    const bool latitudeChecked = latitudePCI &&
        latitudePCI->configRead16(kIOPCIConfigVendorID) == 0x8086 &&
        latitudePCI->configRead16(kIOPCIConfigDeviceID) == 0x7e7b &&
        latitudePCI->getProperty("LatitudeTouchpadResourceFallback") == kOSBooleanTrue;
    if (latitudeChecked && !getProperty("LatitudeI2CCompletionBuild"))
        setProperty("LatitudeI2CCompletionBuild", "test22-linux-stop-idle");
    requestTransferI2C();''')
    needle='''    toggleBusState(kVoodooI2CStateOff);

    if (bus_device.message_error)'''
    replacement='''    // Linux waits for MASTER_ACTIVITY to clear after STOP. An immediate
    // disable can hold SCL low even though STOP was already signalled.
    bool latitudeIdle = true;
    unsigned latitudeLast = 0, latitudeWaited = 0;
    if (latitudeChecked) {
        latitudeIdle = latitudeWaitMasterIdle(
            [&]() -> unsigned { return readRegister(DW_IC_STATUS); },
            [](unsigned us) { IODelay(us); }, latitudeLast, latitudeWaited);
        ++latitude_completion_transfers;
        if (latitudeWaited) ++latitude_completion_waits;
        if (!latitudeIdle) ++latitude_completion_timeouts;
        if (latitudeWaited || !latitudeIdle || !(latitude_completion_transfers & 127)) {
            setProperty("LatitudeI2CCompletionTransfers",latitude_completion_transfers,64);
            setProperty("LatitudeI2CStopIdleWaits",latitude_completion_waits,64);
            setProperty("LatitudeI2CStopIdleTimeouts",latitude_completion_timeouts,64);
            setProperty("LatitudeI2CStopLastStatus",latitudeLast,32);
            setProperty("LatitudeI2CStopWaitUs",latitudeWaited,32);
        }
    }
    IOReturn latitudeDisable = toggleBusState(kVoodooI2CStateOff);
    if (latitudeChecked) {
        bool hasRead = false;
        for (int i=0;i<*number;++i) hasRead |= (messages[i].flags & I2C_M_RD) != 0;
        bool complete = latitudeTransferComplete(bus_device.status,
            bus_device.message_write_index,*number,bus_device.message_read_index,
            bus_device.receive_outstanding,hasRead);
        if (!latitudeIdle || latitudeDisable != kIOReturnSuccess ||
            sleep != THREAD_AWAKENED || !complete) {
            setProperty("LatitudeI2CIncompleteTransfers",++latitude_completion_incomplete,64);
            setProperty("LatitudeI2CCompletionState",bus_device.status,32);
            setProperty("LatitudeI2CCompletionReadIndex",bus_device.message_read_index,32);
            setProperty("LatitudeI2CCompletionWriteIndex",bus_device.message_write_index,32);
            setProperty("LatitudeI2CCompletionOutstanding",bus_device.receive_outstanding,32);
            setProperty("LatitudeI2CCompletionWakeReason",(UInt32)sleep,32);
            // Do not replay writes: a failed/partial transfer may have side effects.
            return kIOReturnIOError;
        }
    }

    if (bus_device.message_error)'''
    s=once(s,needle,replacement)
    p.write_text(s)
    p=folder/'VoodooI2CControllerDriver.hpp';s=p.read_text()
    s=once(s,'    VoodooI2CControllerBusDevice bus_device;','''    UInt64 latitude_completion_transfers = 0;
    UInt64 latitude_completion_waits = 0;
    UInt64 latitude_completion_timeouts = 0;
    UInt64 latitude_completion_incomplete = 0;
    VoodooI2CControllerBusDevice bus_device;''')
    p.write_text(s)
    (out/'completion-ControllerDriver.cpp').write_text((folder/'VoodooI2CControllerDriver.cpp').read_text())
