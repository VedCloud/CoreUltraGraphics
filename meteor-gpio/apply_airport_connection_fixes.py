from apply_report_fixes import once
import subprocess


def body(s, fn):
    a=s.index('\n'+fn+'(');a=s.index('{',a);e=a+1;d=1
    while d:
        if s[e]=='{':d+=1
        elif s[e]=='}':d-=1
        e+=1
    return a,e


def validate_rate_encoding(wifi,out):
    s=(wifi/'itlwm/hal_iwx/ItlIwx.cpp').read_text()
    start=s.index('static void latitude_encode_basic_rates(')
    end=s.index('static void iwx_build_he_sta',start)
    helper=s[start:end]
    test=out/'basic-rate-regression.cpp'
    test.write_text('#include <cstdint>\n#include <cassert>\n#include <cstdio>\n'+helper+r'''
static void check(const uint8_t *rates,unsigned count,uint32_t cck,uint32_t ofdm) {
    uint32_t actual_cck=0,actual_ofdm=0;
    latitude_encode_basic_rates(rates,count,&actual_cck,&actual_ofdm);
    assert(actual_cck==cck && actual_ofdm==ofdm);
    assert((actual_cck & ~0x0fU)==0 && (actual_ofdm & ~0xffU)==0);
}
int main() {
    // Independent firmware wire-index fixtures from Linux rs.h/mac-ctxt.c.
    // Standard basic6/12/24 Mbps must be0x15, not driver's gapped0x25.
    const uint8_t standard5[]={0x8c,18,0x98,36,0xb0,72,96,108};
    check(standard5,sizeof(standard5),0x0f,0x15);
    const uint8_t allOFDM[]={0x8c,0x92,0x98,0xa4,0xb0,0xc8,0xe0,0xec};
    check(allOFDM,sizeof(allOFDM),0x0f,0xff);
    const uint8_t highOnly[]={0xec};
    check(highOnly,sizeof(highOnly),0x0f,0x95);
    const uint8_t cckOnly[]={0x8b,0x96};
    check(cckOnly,sizeof(cckOnly),0x0f,0x15);
    const uint8_t oneMbps[]={0x82};
    check(oneMbps,sizeof(oneMbps),0x01,0x15);
    const uint8_t duplicates[]={0x8c,0x8c,0x98,0xb0,0xfe};
    check(duplicates,sizeof(duplicates),0x0f,0x15);
    check(nullptr,0,0x0f,0x15);
    std::puts("Firmware basic-rate regression fixtures passed:6/12/24=0x15; allOFDM=0xff;54-only=0x95");
}
''')
    exe=out/'basic-rate-regression'
    subprocess.run(['clang++','-std=c++11','-Wall','-Wextra','-Werror',str(test),'-o',str(exe)],check=True)
    subprocess.run([str(exe.resolve())],check=True)


def apply(wifi):
    p=wifi/'itlwm/hal_iwx/ItlIwx.cpp';s=p.read_text()
    # Linux v6.5 fw/api/mac-cfg.h and datapath.h, packed wire layouts.
    anchor='int ItlIwx::\niwx_enable_txq('
    types='''static void latitude_encode_basic_rates(const uint8_t *rates, unsigned count,
    uint32_t *cck_rates, uint32_t *ofdm_rates) {
    // Firmware indexes are contiguous physical legacy rates. The driver's
    // internal iwx_rates indexes also contain MCS entries and cannot be used.
    const uint8_t cck_values[4]={2,4,11,22};
    const uint8_t ofdm_values[8]={12,18,24,36,48,72,96,108};
    uint32_t cck=0,ofdm=0;
    unsigned lowest_cck=4,lowest_ofdm=8;
    for(unsigned i=0;i<count;i++) {
        if(!(rates[i]&0x80)) continue;
        uint8_t value=rates[i]&0x7f;
        for(unsigned bit=0;bit<4;bit++) if(value==cck_values[bit]) {
            cck|=1U<<bit;
            if(bit<lowest_cck) lowest_cck=bit;
        }
        for(unsigned bit=0;bit<8;bit++) if(value==ofdm_values[bit]) {
            ofdm|=1U<<bit;
            if(bit<lowest_ofdm) lowest_ofdm=bit;
        }
    }
    // Intel/Linux mandatory control-response rates: OFDM6/12/24 and lower CCK.
    if(lowest_ofdm>4) ofdm|=1U<<4;
    if(lowest_ofdm>2) ofdm|=1U<<2;
    ofdm|=1;
    for(unsigned bit=1;bit<4;bit++) if(bit<lowest_cck) cck|=1U<<bit;
    cck|=1;
    *cck_rates=cck; *ofdm_rates=ofdm;
}
static void iwx_build_he_sta(const struct ieee80211_node *, struct iwx_he_sta_context_cmd *);
static bool latitude_mld(struct iwx_softc *sc) {
    return sc->sc_pcitag->configRead16(kIOPCIConfigDeviceID) == 0x7e40 &&
        strcmp(sc->sc_fwname, "iwlwifi-ma-b0-gf-a0-83.ucode") == 0 &&
        isset(sc->sc_enabled_capa, 110);
}
struct latitude_link_v1 {
    uint32_t action, link_id, mac_id, phy_id;
    uint8_t addr[6]; uint16_t reserved_addr;
    uint32_t modify_mask, active, listen_lmac, cck_rates, ofdm_rates;
    uint32_t preamble, slot, protection, qos;
    struct iwx_ac_qos ac[5];
    uint8_t htc_ext, ecwmin, ecwmax, ndp;
    struct iwx_he_backoff_conf trig[4];
    uint32_t bi, dtim;
    uint16_t puncture, rts;
    uint32_t flags, flags_mask;
    uint8_t ref_addr[6]; uint16_t reserved_ref;
    uint8_t bssid_index, color, spec_link, reserved;
    uint8_t ibss_addr[6]; uint16_t reserved_ibss;
    uint32_t reserved1[8];
} __packed;
struct latitude_sta_v1 {
    uint32_t sta_id, link_id;
    uint8_t peer_mld[6]; uint16_t reserved_mld;
    uint8_t peer_link[6]; uint16_t reserved_link;
    uint32_t type, assoc_id, beamform, mfp, mimo, mimo_protection;
    uint32_t ack_enabled, trig_alloc, spacing, max_size, sp_length, uapsd;
    uint8_t pkt_ext[2][5][2];
    uint32_t htc;
} __packed;
struct latitude_queue_v3 {
    uint32_t operation, sta_mask;
    uint8_t tid, reserved[3];
    uint32_t flags, cb_size;
    uint64_t bc_addr, tfd_addr;
} __packed;
struct latitude_key_v1 {
    uint32_t action, sta_mask, key_id, flags;
    uint8_t key[32], mic_rx[8], mic_tx[8];
    uint64_t rx_seq, tx_seq;
} __packed;
static_assert(sizeof(latitude_link_v1)==208, "MLD link v1 ABI");
static_assert(sizeof(latitude_sta_v1)==96, "MLD station v1 ABI");
static_assert(sizeof(latitude_queue_v3)==36, "MLD queue v3 ABI");
static_assert(sizeof(latitude_key_v1)==80, "MLD security key v1 ABI");
static_assert(sizeof(struct iwx_tx_cmd_gen3)==28, "TX versions8/10 shared ABI");

'''
    s=once(s,anchor,types+anchor)
    a,e=body(s,'iwx_binding_cmd');b=s[a:e]
    cut=b.index('    struct iwx_binding_cmd cmd;')
    b='{\n'+b[cut:]
    b=once(b,'    struct iwx_binding_cmd cmd;', '''    if (latitude_mld(sc)) {
        if (!in->in_phyctxt) return EINVAL;
        struct latitude_link_v1 link;
        memset(&link,0,sizeof(link));
        link.link_id=htole32(in->in_id);
        link.mac_id=htole32(in->in_id);
        link.phy_id=htole32(in->in_phyctxt->id);
        IEEE80211_ADDR_COPY(link.addr,sc->sc_ic.ic_myaddr);
        struct iwx_mac_ctx_cmd legacy;
        memset(&legacy,0,sizeof(legacy));
        iwx_mac_ctxt_cmd_common(sc,in,&legacy,IWX_FW_CTXT_ACTION_MODIFY);
        uint32_t cck_basic,ofdm_basic;
        latitude_encode_basic_rates(in->in_ni.ni_rates.rs_rates,
            in->in_ni.ni_rates.rs_nrates,&cck_basic,&ofdm_basic);
        link.cck_rates=htole32(cck_basic); link.ofdm_rates=htole32(ofdm_basic);
        link.preamble=htole32(le32toh(legacy.cck_short_preamble)!=0);
        link.slot=htole32(le32toh(legacy.short_slot)!=0);
        uint32_t old_protection=le32toh(legacy.protection_flags), new_protection=0;
        if(old_protection & IWX_MAC_PROT_FLG_TGG_PROTECT) new_protection|=1U<<0;
        if(old_protection & IWX_MAC_PROT_FLG_HT_PROT) new_protection|=1U<<1;
        if(old_protection & IWX_MAC_PROT_FLG_FAT_PROT) new_protection|=1U<<2;
        if(old_protection & IWX_MAC_PROT_FLG_SELF_CTS_EN) new_protection|=1U<<3;
        link.protection=htole32(new_protection); link.qos=legacy.qos_flags;
        memcpy(link.ac,legacy.ac,sizeof(legacy.ac));
        link.bi=htole32(in->in_ni.ni_intval);
        link.dtim=htole32(in->in_ni.ni_intval*in->in_ni.ni_dtimperiod);
        link.flags=htole32(1); link.flags_mask=htole32(1); // no HE color filtering initially
        const char *link_stage="prepare";
        auto send_link=[&](uint32_t act) -> int {
            link.action=htole32(act);
            int result=iwx_send_cmd_pdu(sc,iwx_cmd_id(0x09,IWX_MAC_CONF_GROUP,0),0,sizeof(link),&link);
            IOService *parent=getController()?getController()->getProvider():nullptr;
            if(parent) {
                parent->setProperty("LatitudeWiFiLinkResult",(UInt32)result,32);
                parent->setProperty("LatitudeWiFiLinkAction",act,32);
                parent->setProperty("LatitudeWiFiLinkStage",link_stage);
                parent->setProperty("LatitudeWiFiLinkModifyMask",le32toh(link.modify_mask),32);
                parent->setProperty("LatitudeWiFiLinkPhyID",le32toh(link.phy_id),32);
                parent->setProperty("LatitudeWiFiBasicRateEncoding","contiguous-physical-rates");
                if(result && !parent->getProperty("LatitudeWiFiLinkFirstFailureStage")) {
                    parent->setProperty("LatitudeWiFiLinkFirstFailureStage",link_stage);
                    parent->setProperty("LatitudeWiFiLinkFirstFailureResult",(UInt32)result,32);
                    parent->setProperty("LatitudeWiFiLinkFirstFailureAction",act,32);
                    parent->setProperty("LatitudeWiFiLinkFirstFailureMask",le32toh(link.modify_mask),32);
                }
            }
            return result;
        };
        int result=0;
        if(action==IWX_FW_CTXT_ACTION_ADD) {
            // Linux creates an inactive infrastructure link before assigning
            // PHY/rates/QoS. ADD does not carry MODIFY-only configuration.
            struct latitude_link_v1 configured=link;
            memset(&link,0,sizeof(link));
            link.link_id=configured.link_id;
            link.mac_id=configured.mac_id;
            link.phy_id=htole32(IWX_FW_CTXT_INVALID);
            IEEE80211_ADDR_COPY(link.addr,sc->sc_ic.ic_myaddr);
            link_stage="add-inactive";
            result=send_link(IWX_FW_CTXT_ACTION_ADD);
            IOService *parent=getController()?getController()->getProvider():nullptr;
            if(parent) {
                parent->setProperty("LatitudeWiFiLinkAddResult",(UInt32)result,32);
                parent->setProperty("LatitudeWiFiLinkAddLayout","linux-inactive-minimal");
            }
            if(result) return result;
            // Attach the PHY and activate independently of rates/QoS/HE.
            link=configured;
            memset(&link,0,sizeof(link));
            link.link_id=configured.link_id; link.mac_id=configured.mac_id;
            link.phy_id=configured.phy_id;
            IEEE80211_ADDR_COPY(link.addr,sc->sc_ic.ic_myaddr);
            // Linux mld-mac80211: assign PHY in inactive MODIFY first.
            link.modify_mask=0; link.active=0;
            link_stage="assign-phy-inactive";
            result=send_link(IWX_FW_CTXT_ACTION_MODIFY);
            if(parent) parent->setProperty("LatitudeWiFiLinkAssignPhyResult",(UInt32)result,32);
            if(result) {
                link_stage="rollback-remove";
                send_link(IWX_FW_CTXT_ACTION_REMOVE);
                return result;
            }
            // Then ACTIVE | RATES_INFO, with the mandatory basic rates.
            link.cck_rates=configured.cck_rates; link.ofdm_rates=configured.ofdm_rates;
            link.preamble=configured.preamble; link.slot=configured.slot;
            link.modify_mask=htole32(3); link.active=htole32(1);
            link_stage="activate-with-basic-rates";
            result=send_link(IWX_FW_CTXT_ACTION_MODIFY);
            if(parent) parent->setProperty("LatitudeWiFiLinkActivateResult",(UInt32)result,32);
            if(result) {
                link_stage="rollback-remove";
                link.modify_mask=0; link.active=0;
                send_link(IWX_FW_CTXT_ACTION_REMOVE);
                return result;
            }
            link=configured;
        }
        uint32_t modifications=0x0e; // rates, protection, QoS; activation is separate
        if(action==IWX_FW_CTXT_ACTION_ADD) in->latitude_beacon_timing_set=false;
        bool timing=(in->in_ni.ni_associd && in->in_ni.ni_dtimperiod &&
            !in->latitude_beacon_timing_set && action!=IWX_FW_CTXT_ACTION_REMOVE);
        if(timing) modifications|=0x10;
        link.modify_mask=htole32(modifications);
        link.active=htole32(action!=IWX_FW_CTXT_ACTION_REMOVE);
        link_stage="configure-active-link";
        if(action==IWX_FW_CTXT_ACTION_REMOVE) {
            uint32_t id=link.link_id, mac=link.mac_id, phy=link.phy_id;
            memset(&link,0,sizeof(link));
            link.link_id=id;link.mac_id=mac;link.phy_id=phy;
            IEEE80211_ADDR_COPY(link.addr,sc->sc_ic.ic_myaddr);
            link.modify_mask=htole32(1);
            link_stage="deactivate-phy-only";
        }
        result=send_link(IWX_FW_CTXT_ACTION_MODIFY);
        if(result && action==IWX_FW_CTXT_ACTION_ADD) {
            link_stage="rollback-remove";
            link.active=0; link.modify_mask=0; send_link(IWX_FW_CTXT_ACTION_REMOVE);
        }
        if(result) return result;
        if(timing) in->latitude_beacon_timing_set=true;
        if(action==IWX_FW_CTXT_ACTION_REMOVE) {
            in->latitude_beacon_timing_set=false;
            link_stage="remove-inactive";
            link.modify_mask=0;
            return send_link(action);
        }
        return 0;
    }
    struct iwx_binding_cmd cmd;''')
    s=s[:a]+b+s[e:]
    a,e=body(s,'iwx_add_sta_cmd');b=s[a:e]
    b=once(b,'    memset(&add_sta_cmd, 0, sizeof(add_sta_cmd));', '''    if(latitude_mld(sc)) {
        struct latitude_sta_v1 sta;
        memset(&sta,0,sizeof(sta));
        sta.sta_id=htole32(IWX_STATION_ID); sta.link_id=htole32(in->in_id);
        IEEE80211_ADDR_COPY(sta.peer_mld,in->in_macaddr);
        IEEE80211_ADDR_COPY(sta.peer_link,in->in_macaddr);
        sta.assoc_id=htole32(in->in_ni.ni_associd & 0x3fff);
        sta.mimo=htole32(in->in_ni.ni_rx_nss>1);
        sta.sp_length=htole32(128);
        sta.spacing=htole32((ic->ic_ampdu_params & IEEE80211_AMPDU_PARAM_SS)>>2);
        sta.max_size=htole32(ic->ic_ampdu_params & IEEE80211_AMPDU_PARAM_LE);
        memset(sta.pkt_ext,7,sizeof(sta.pkt_ext)); // PPE NONE
        int result=iwx_send_cmd_pdu(sc,iwx_cmd_id(0x0a,IWX_MAC_CONF_GROUP,0),0,sizeof(sta),&sta);
        IOService *parent=getController()?getController()->getProvider():nullptr;
        if(parent) parent->setProperty("LatitudeWiFiStationResult",(UInt32)result,32);
        if(!result) sc->sc_flags|=IWX_FLAG_STA_ACTIVE;
        return result;
    }
    memset(&add_sta_cmd, 0, sizeof(add_sta_cmd));''')
    s=s[:a]+b+s[e:]
    a,e=body(s,'iwx_rm_sta_cmd');b=s[a:e]
    b=once(b,'    memset(&rm_sta_cmd, 0, sizeof(rm_sta_cmd));', '''    if(latitude_mld(sc)) {
        // Flush happens in the caller before removing firmware-owned queues.
        for(int tid=0;tid<=IEEE80211_NUM_TID;tid++) {
            bool management=tid==IEEE80211_NUM_TID;
            int queue=management ? sc->first_data_qid : sc->sc_tid_data[tid].qid;
            if(queue==0 || queue==IWX_INVALID_QUEUE ||
               (!management && queue==sc->first_data_qid)) continue;
            struct latitude_queue_v3 remove;
            memset(&remove,0,sizeof(remove));
            remove.operation=htole32(1);
            remove.sta_mask=htole32(1U<<IWX_STATION_ID);
            remove.tid=management ? IWX_MGMT_TID : tid;
            int result=iwx_send_cmd_pdu(sc,iwx_cmd_id(0x17,IWX_DATA_PATH_GROUP,0),0,sizeof(remove),&remove);
            if(result) return result;
            if(!management) sc->sc_tid_data[tid].qid=IWX_INVALID_QUEUE;
        }
        uint32_t sta=htole32(IWX_STATION_ID);
        int result=iwx_send_cmd_pdu(sc,iwx_cmd_id(0x0c,IWX_MAC_CONF_GROUP,0),0,sizeof(sta),&sta);
        if(!result) sc->sc_flags &= ~IWX_FLAG_STA_ACTIVE;
        return result;
    }
    memset(&rm_sta_cmd, 0, sizeof(rm_sta_cmd));''')
    s=s[:a]+b+s[e:]
    # Every allocation path uses the same new scheduler ABI. Existing response
    # validation, DMA ownership and dynamic qid handling remain unchanged.
    for fn in ['iwx_enable_txq','iwx_tvqm_enable_txq']:
        a,e=body(s,fn);b=s[a:e]
        b=once(b,'    hcmd.data[0] = &cmd;', '''    struct latitude_queue_v3 modern_queue;
    memset(&modern_queue,0,sizeof(modern_queue));
    hcmd.data[0] = &cmd;''')
        b=once(b,'    hcmd.len[0] = sizeof(cmd);', '''    hcmd.len[0] = sizeof(cmd);
    if(latitude_mld(sc)) {
        modern_queue.sta_mask=htole32(1U << cmd.sta_id);
        modern_queue.tid=cmd.tid;
        modern_queue.cb_size=cmd.cb_size;
        modern_queue.bc_addr=cmd.byte_cnt_addr; modern_queue.tfd_addr=cmd.tfdq_addr;
        hcmd.id=iwx_cmd_id(0x17,IWX_DATA_PATH_GROUP,0);
        hcmd.data[0]=&modern_queue; hcmd.len[0]=sizeof(modern_queue);
    }''')
        # Declaring the new payload after gotos would cross initialization.
        b=b.replace('    struct latitude_queue_v3 modern_queue;\n    memset(&modern_queue,0,sizeof(modern_queue));\n','')
        b=b.replace('{','{\n    struct latitude_queue_v3 modern_queue;\n    memset(&modern_queue,0,sizeof(modern_queue));',1)
        s=s[:a]+b+s[e:]
    a,e=body(s,'iwx_enable_mgmt_queue');b=s[a:e]
    b=once(b,'    int err;', '''    if(latitude_mld(sc)) {
        int queue=iwx_tvqm_enable_txq(sc,IWX_MGMT_TID,0,IWX_DEFAULT_QUEUE_SIZE);
        IOService *parent=getController()?getController()->getProvider():nullptr;
        if(parent) parent->setProperty("LatitudeWiFiMgmtQueueResult",(UInt32)queue,32);
        if(queue<0) return -queue;
        sc->first_data_qid=queue;
        return 0;
    }
    int err;''')
    s=s[:a]+b+s[e:]
    # Modern response payload must enter existing checked WANT_RESP copy path.
    s=once(s,'            case IWX_SCD_QUEUE_CFG: {', '''            case IWX_WIDE_ID(IWX_DATA_PATH_GROUP,0x17):
            case IWX_SCD_QUEUE_CFG: {''')
    s=once(s,'            case IWX_WIDE_ID(IWX_MAC_CONF_GROUP, 0x08): {', '''            case IWX_WIDE_ID(IWX_MAC_CONF_GROUP,0x09):
            case IWX_WIDE_ID(IWX_MAC_CONF_GROUP,0x0a):
            case IWX_WIDE_ID(IWX_MAC_CONF_GROUP,0x0c):
            case IWX_WIDE_ID(IWX_DATA_PATH_GROUP,0x18):
                break; // ACK -> existing queue/index checked completion
            case IWX_WIDE_ID(IWX_MAC_CONF_GROUP, 0x08): {''')
    # New firmware moves encryption keys to SEC_KEY instead of ADD_STA_KEY.
    for fn,remove in [('iwx_set_key',False),('iwx_delete_key',True)]:
        a,e=body(s,fn);b=s[a:e]
        anchor='    if (k->k_cipher != IEEE80211_CIPHER_CCMP) {'
        code='''    if(latitude_mld(sc) && k->k_cipher==IEEE80211_CIPHER_CCMP) {
        struct latitude_key_v1 modern;
        memset(&modern,0,sizeof(modern));
        modern.action=htole32(%s);
        modern.sta_mask=htole32(1U<<IWX_STATION_ID);
        modern.key_id=htole32(k->k_id);
        modern.flags=htole32(2 | ((k->k_flags & IEEE80211_KEY_GROUP)?0x40:0));
        %s
        int result=that->iwx_send_cmd_pdu(sc,iwx_cmd_id(0x18,IWX_DATA_PATH_GROUP,0),0,sizeof(modern),&modern);
        IOService *parent=that->getController()?that->getController()->getProvider():nullptr;
        if(parent) parent->setProperty("LatitudeWiFiKeyResult",(UInt32)result,32);
        %s
    }
'''%('IWX_FW_CTXT_ACTION_REMOVE' if remove else 'IWX_FW_CTXT_ACTION_ADD',
     '' if remove else 'memcpy(modern.key,k->k_key,MIN(sizeof(modern.key),k->k_len)); modern.tx_seq=htole64(k->k_tsc); modern.rx_seq=htole64(k->k_rsc[0]);',
     'return;' if remove else 'return result;')
        b=once(b,anchor,code+anchor);s=s[:a]+b+s[e:]
    # Link receives associated beacon/rate/QoS updates when MAC changes.
    s=once(s,'        return result;\n    }\n\n    memset(&cmd, 0, sizeof(cmd));', '''        if(!result && action==IWX_FW_CTXT_ACTION_MODIFY && (sc->sc_flags & IWX_FLAG_BINDING_ACTIVE))
            result=iwx_binding_cmd(sc,in,IWX_FW_CTXT_ACTION_MODIFY);
        return result;
    }

    memset(&cmd, 0, sizeof(cmd));''')
    s=once(s,'fwqid <= IWX_QID_MGMT || sc->txq[fwqid].queued',
        '(latitude_mld(sc) ? fwqid == IWX_DQA_CMD_QUEUE : fwqid <= IWX_QID_MGMT) || sc->txq[fwqid].queued')
    a,e=body(s,'iwx_drain_sta');b=s[a:e]
    b=b.replace('{','''{
    if(latitude_mld(sc)) {
        uint32_t disable[2]={htole32(IWX_STATION_ID),htole32(drain!=0)};
        return iwx_send_cmd_pdu(sc,iwx_cmd_id(0x0d,IWX_MAC_CONF_GROUP,0),0,sizeof(disable),disable);
    }
''',1);s=s[:a]+b+s[e:]
    s=once(s,'            case IWX_WIDE_ID(IWX_MAC_CONF_GROUP,0x0c):',
        '            case IWX_WIDE_ID(IWX_MAC_CONF_GROUP,0x0c):\n            case IWX_WIDE_ID(IWX_MAC_CONF_GROUP,0x0d):')
    # MLD scheduling is configured per link, without legacy binding quotas.
    a,e=body(s,'iwx_update_quotas');b=s[a:e]
    b=b.replace('{','{\n    if(latitude_mld(sc)) return 0;',1);s=s[:a]+b+s[e:]
    # Clearing telemetry is optional; avoid old statistics ABI on MLD firmware.
    a,e=body(s,'iwx_clear_statistics');b=s[a:e]
    b=b.replace('{','{\n    if(latitude_mld(sc)) return 0;',1);s=s[:a]+b+s[e:]
    # HE station/link fields are embedded in the MLD APIs, not STA_HE_CTXT.
    s=once(s,'        memset(sta.pkt_ext,7,sizeof(sta.pkt_ext)); // PPE NONE', '''        memset(sta.pkt_ext,7,sizeof(sta.pkt_ext)); // PPE NONE
        sta.mfp=htole32((in->in_ni.ni_flags & IEEE80211_NODE_MFP)!=0);
        if(in->in_ni.ni_flags & IEEE80211_NODE_HE) {
            struct iwx_he_sta_context_cmd he;
            iwx_build_he_sta(&in->in_ni,&he);
            for(int n=0;n<2;n++) for(int bw=0;bw<4;bw++)
                memcpy(sta.pkt_ext[n][bw],he.pkt_ext[n][bw],2);
            sta.htc=he.htc_flags;
            sta.ack_enabled=htole32((le32toh(he.flags)&IWX_HE_ACK_ENABLED)!=0);
        }''')
    s=once(s,'        link.bi=htole32(in->in_ni.ni_intval);', '''        if(in->in_ni.ni_flags & IEEE80211_NODE_HE) {
            struct iwx_he_sta_context_cmd he;
            iwx_build_he_sta(&in->in_ni,&he);
            link.htc_ext=he.htc_trig_based_pkt_ext;
            link.ecwmin=he.rand_alloc_ecwmin; link.ecwmax=he.rand_alloc_ecwmax;
            memcpy(link.trig,he.trig_based_txf,sizeof(link.trig));
            link.color=he.bss_color; link.rts=he.frame_time_rts_th;
        }
        link.bi=htole32(in->in_ni.ni_intval);''')
    s=once(s,'        link.modify_mask=htole32(modifications);',
        '        if(in->in_ni.ni_flags & IEEE80211_NODE_HE) modifications|=0x60;\n        link.modify_mask=htole32(modifications);')
    s=once(s,'    uint8_t ver = iwx_lookup_cmd_ver(sc, IWX_DATA_PATH_GROUP, IWX_STA_HE_CTXT_CMD);', '''    if(latitude_mld(sc)) {
        struct iwx_node *in=(struct iwx_node *)ni;
        int result=iwx_add_sta_cmd(sc,in,1);
        if(!result) result=iwx_binding_cmd(sc,in,IWX_FW_CTXT_ACTION_MODIFY);
        return result;
    }
    uint8_t ver = iwx_lookup_cmd_ver(sc, IWX_DATA_PATH_GROUP, IWX_STA_HE_CTXT_CMD);''')
    p.write_text(s)
    p=wifi/'itlwm/hal_iwx/if_iwxvar.h';s=p.read_text()
    s=once(s,'struct iwx_node {', 'struct iwx_node {\n    bool latitude_beacon_timing_set;')
    # ieee80211_node must remain at offset zero for net80211 casts.
    s=s.replace('struct iwx_node {\n    bool latitude_beacon_timing_set;\n\tstruct ieee80211_node in_ni;',
        'struct iwx_node {\n\tstruct ieee80211_node in_ni;\n    bool latitude_beacon_timing_set;')
    p.write_text(s)
