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
    return awake && ready && frames && legacy && idle >= 1024 && attempts < 3;
}
#endif
