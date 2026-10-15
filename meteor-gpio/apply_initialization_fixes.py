from pathlib import Path
import re

def once(s,old,new):
    assert s.count(old)==1,(old[:90],s.count(old))
    return s.replace(old,new)

def apply(i2c,wifi):
    p=wifi/'itlwm/hal_iwx/if_iwxvar.h'
    s=p.read_text()
    match=re.search(r'([ \t]+(?:int|uint32_t|u32)\s+sc_init_complete;)',s)
    assert match
    s=s.replace(match.group(1),match.group(1)+'\n    volatile bool latitude_pnvm_complete;\n    volatile uint32_t latitude_pnvm_status;',1)
    p.write_text(s)
    p=wifi/'itlwm/hal_iwx/ItlIwx.cpp'
    s=p.read_text()
    # Completion predicates must be checked around sleeping: notification can
    # precede the sleep, or arrive before a timeout is observed by the waiter.
    s=once(s,'    err = tsleep_nsec(&sc->sc_uc, 0, "iwxuc", SEC_TO_NSEC(1));','''    err = 0;
    if (!sc->sc_uc.uc_intr)
        err = tsleep_nsec(&sc->sc_uc, 0, "iwxuc", SEC_TO_NSEC(1));
    if (sc->sc_uc.uc_intr && sc->sc_uc.uc_ok) err = 0;''')
    start=s.index('iwx_run_init_mvm_ucode(struct iwx_softc')
    end=s.index('\nint ItlIwx::',start)
    body=s[start:end]
    body=once(body,'    err = tsleep_nsec(&sc->sc_init_complete, 0, "iwxinit", SEC_TO_NSEC(2));','''    err = 0;
    if ((sc->sc_init_complete & wait_flags) != wait_flags)
        err = tsleep_nsec(&sc->sc_init_complete, 0, "iwxinit", SEC_TO_NSEC(2));
    if ((sc->sc_init_complete & wait_flags) == wait_flags) err = 0;
    else if (!err) err = ETIMEDOUT;''')
    s=s[:start]+body+s[end:]
    start=s.index('iwx_load_pnvm(struct iwx_softc')
    end=s.index('\nstatic uint32_t',start)
    body=s[start:end]
    body=once(body,'    /* kick the doorbell */','''    sc->latitude_pnvm_complete = false;
    sc->latitude_pnvm_status = 0xffffffff;
    /* kick the doorbell */''')
    body=once(body,'    err = tsleep_nsec(&sc->sc_init_complete, 0, "iwxinit", SEC_TO_NSEC(2));','''    err = 0;
    if (!sc->latitude_pnvm_complete)
        err = tsleep_nsec(&sc->sc_init_complete, 0, "iwxinit", SEC_TO_NSEC(2));
    if (sc->latitude_pnvm_complete)
        err = sc->latitude_pnvm_status == 0 ? 0 : EIO;
    else if (!err) err = ETIMEDOUT;
    {
        IOService *parent = getController() ? getController()->getProvider() : nullptr;
        if (parent) {
            parent->setProperty("LatitudeWiFiPNVMComplete", sc->latitude_pnvm_complete);
            parent->setProperty("LatitudeWiFiPNVMStatus", sc->latitude_pnvm_status, 32);
        }
    }''')
    s=s[:start]+body+s[end:]
    s=once(s,'''                wakeupOn(&sc->sc_init_complete);
                struct iwl_pnvm_init_complete_ntfy *pnvm_ntf;''','''                struct iwl_pnvm_init_complete_ntfy *pnvm_ntf;''')
    s=once(s,'                XYLog("PNVM complete notification received with status 0x%0x\\n", le32toh(pnvm_ntf->status));','''                sc->latitude_pnvm_status = le32toh(pnvm_ntf->status);
                sc->latitude_pnvm_complete = true;
                wakeupOn(&sc->sc_init_complete);
                XYLog("PNVM complete notification received with status 0x%0x\\n", le32toh(pnvm_ntf->status));''')
    # Wrap markers in blocks so goto cleanup paths cannot cross initializations.
    for fn in ['iwx_preinit','iwx_run_init_mvm_ucode','iwx_load_ucode_wait_alive','iwx_load_pnvm','iwx_load_firmware']:
        start=s.index(fn+'(struct iwx_softc *sc')
        begin=s.index('{',start)
        depth=1; end=begin+1
        while depth:
            if s[end]=='{': depth+=1
            elif s[end]=='}': depth-=1
            end+=1
        body=s[begin:end]
        pattern=r'(?m)^    err = ((?:iwx_\w+|tsleep_nsec)\([\s\S]*?\);)'
        def instrument(m):
            call=m.group(1); operation=call.split('(',1)[0]
            marker=fn+'/'+operation
            before='''    {
        IOService *parent = getController() ? getController()->getProvider() : nullptr;
        if (parent) parent->setProperty("LatitudeWiFiInitStage", "%s");
    }
'''%marker
            after='''
    {
        IOService *parent = getController() ? getController()->getProvider() : nullptr;
        if (parent) {
            parent->setProperty("LatitudeWiFiInitResult", (UInt32)err, 32);
            if (err && !parent->getProperty("LatitudeWiFiFailureStage")) {
                parent->setProperty("LatitudeWiFiFailureStage", "%s");
                parent->setProperty("LatitudeWiFiFailureCode", (UInt32)err, 32);
            }
            parent->setProperty("LatitudeWiFiAliveReceived", sc->sc_uc.uc_intr != 0);
            parent->setProperty("LatitudeWiFiAliveValid", sc->sc_uc.uc_ok != 0);
            parent->setProperty("LatitudeWiFiInitCompleteFlags", sc->sc_init_complete, 32);
        }
    }'''%marker
            return before+'    err = '+call+after
        body=re.sub(pattern,instrument,body)
        s=s[:begin]+body+s[end:]
    p.write_text(s)
    p=i2c/'VoodooI2C/VoodooI2C/VoodooI2CDevice/VoodooI2CDeviceNub.cpp'
    s=p.read_text()
    s=once(s,'    return command_gate->attemptAction(OSMemberFunctionCast(IOCommandGate::Action, this, &VoodooI2CDeviceNub::readI2CGated), values, &length);','''    IOReturn result = command_gate->attemptAction(OSMemberFunctionCast(IOCommandGate::Action, this, &VoodooI2CDeviceNub::readI2CGated), values, &length);
    OSNumber *previous = OSDynamicCast(OSNumber, getProperty("LatitudeI2CReadCount"));
    UInt64 count = previous ? previous->unsigned64BitValue() + 1 : 1;
    if (count <= 16 || (count & (count - 1)) == 0 || result != kIOReturnSuccess) {
        setProperty("LatitudeI2CReadResult", (UInt32)result, 32);
        setProperty("LatitudeI2CReadLength", length, 16);
    }
    setProperty("LatitudeI2CReadCount", count, 64);
    if (result == kIOReturnSuccess && length == 24) {
        UInt16 payload_length = values[0] | (values[1] << 8);
        if (payload_length > 2 && payload_length <= length) {
            OSNumber *previous_input = OSDynamicCast(OSNumber, getProperty("LatitudeI2CInputCount"));
            UInt64 inputs = previous_input ? previous_input->unsigned64BitValue() + 1 : 1;
            setProperty("LatitudeI2CInputCount", inputs, 64);
            setProperty("LatitudeI2CLastInput", values, payload_length);
        }
    }
    return result;''')
    p.write_text(s)
