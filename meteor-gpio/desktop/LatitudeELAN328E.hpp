#ifndef LATITUDE_ELAN328E_HPP
#define LATITUDE_ELAN328E_HPP
// Exact 04f3:328e descriptor: report54, 224 payload bits, five 40-bit contacts.
struct LatitudeELANContact {
    unsigned id, x, y;
    bool confidence, tip;
};
struct LatitudeELANFrame {
    unsigned count, scan;
    bool button;
    LatitudeELANContact contacts[5];
};
static bool latitudeDecodeELAN(const unsigned char *b, unsigned length, LatitudeELANFrame &f) {
    if (!b || length != 29 || b[0] != 0x54 || (b[1] >> 4) > 5)
        return false;
    f = {};
    f.count = b[1] >> 4;
    f.button = (b[1] & 1) != 0;
    f.scan = b[2] | (unsigned(b[3]) << 8);
    unsigned ids = 0;
    for (unsigned i = 0; i < f.count; ++i) {
        const unsigned char *p = b + 4 + 5*i;
        LatitudeELANContact &c = f.contacts[i];
        c.confidence = (p[0] & 1) != 0;
        c.tip = (p[0] & 2) != 0;
        c.id = p[0] >> 4;
        c.x = p[1] | (unsigned(p[2]) << 8);
        c.y = p[3] | (unsigned(p[4]) << 8);
        if ((ids & (1u << c.id)) || (c.tip && (c.x > 3512 || c.y > 2002)))
            return false;
        ids |= 1u << c.id;
    }
    return true;
}
static bool latitudeELANShouldRecover(bool awake, bool ready, unsigned long long frames,
    bool legacy, unsigned long long idle, unsigned attempts) {
    (void)legacy; // A valid legacy companion packet is not required for a stall.
    return awake && ready && frames && idle >= 1024 && attempts < 3;
}
static bool latitudeELANInputCommand(unsigned char *b, unsigned command, unsigned data) {
    if (!b || command > 65535 || data > 65535) return false;
    b[0]=command; b[1]=command>>8;
    b[2]=0x1f; b[3]=0x02; b[4]=0x54; // INPUT GET_REPORT, extended ID84.
    b[5]=data; b[6]=data>>8;
    return true;
}
static bool latitudeELANWireFrame(const unsigned char *b, unsigned n) {
    if (!b || n != 31 || b[0] != 31 || b[1] != 0) return false;
    LatitudeELANFrame f;
    return latitudeDecodeELAN(b+2,29,f);
}
static bool latitudeELANFeatureCommand(unsigned char *b, unsigned command, unsigned data, unsigned id) {
    if (!b || command>65535 || data>65535 || id>14) return false;
    b[0]=command;b[1]=command>>8;b[2]=0x30|id;b[3]=2;b[4]=data;b[5]=data>>8;
    return true;
}
static bool latitudeELANFeatureReply(const unsigned char *b, unsigned n, unsigned id, unsigned payload) {
    return b && payload>=1 && payload<=257 && n==payload+2 &&
        (unsigned(b[0])|(unsigned(b[1])<<8))==n && b[2]==id;
}
#endif
