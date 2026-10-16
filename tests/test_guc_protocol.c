#include <assert.h>
#include <string.h>
#include "../port/guc_protocol.h"

int main(void)
{
    uint32_t out[4] = {0};
    const uint32_t expected[4] = {0x508, 0x09060002, 0xa0f800, 0};
    assert(cug_guc_self_config(0x906, 0xa0f800, 2, out, 4));
    assert(memcmp(out, expected, sizeof(out)) == 0);
    assert(!cug_guc_self_config(0x906, UINT64_MAX, 1, out, 4));
    assert(!cug_guc_self_config(0x906, 0, 3, out, 4));
    assert(!cug_guc_self_config(0x906, 0, 2, out, 3));
    assert(!cug_guc_self_config(0x906, 0, 2, NULL, 4));
    assert(memcmp(out, expected, sizeof(out)) == 0);
    assert(cug_guc_self_config(0x902, UINT64_C(0x123456780), 2, out, 4));
    assert(out[2] == 0x23456780 && out[3] == 1);
    assert(cug_guc_self_config(0x904, UINT32_MAX, 1, out, 4));
    assert(out[2] == UINT32_MAX && out[3] == 0);
    assert(cug_guc_ctb_control(1, out, 4));
    assert(out[0] == 0x4509 && out[1] == 1);
    assert(!cug_guc_ctb_control(2, out, 4));
    assert(!cug_guc_ctb_control(0, out, 1));
    assert(out[0] == 0x4509 && out[1] == 1);
    assert(sizeof(struct cug_guc_ctb_descriptor) == 64);
    return 0;
}
