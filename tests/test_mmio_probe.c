#include <assert.h>
#include "../port/mmio_probe_policy.h"
int main(void)
{
    /* Exact-end access is permitted, a one-byte overrun is not. */
    assert(cug_probe_read_allowed(CUG_GRAPHICS_GMD_ID, 0xd90));
    assert(!cug_probe_read_allowed(CUG_GRAPHICS_GMD_ID, 0xd8f));
    assert(cug_probe_read_allowed(CUG_MEDIA_GMD_ID, 0x380d90));
    assert(!cug_probe_read_allowed(CUG_MEDIA_GMD_ID, 0x380d8f));
    assert(!cug_probe_read_allowed(CUG_GRAPHICS_GMD_ID, 0));
    assert(!cug_probe_read_allowed(CUG_MEDIA_GMD_ID, 3));
    /* GuC status, GGTT, and adjacent/unaligned addresses are excluded. */
    assert(!cug_probe_read_allowed(0xc000, 0x1000000));
    assert(!cug_probe_read_allowed(0x800000, 0x1000000));
    assert(!cug_probe_read_allowed(0xd8d, ~0ull));
    assert(!cug_probe_read_allowed(0xffffffffu, ~0ull));
    assert(cug_gmd_arch(0x03118008u) == 12);
    assert(cug_gmd_release(0x03118008u) == 70);
    assert(cug_gmd_revision(0x03118008u) == 8);
    assert(cug_gmd_value_valid(0x03118008u));
    assert(cug_gmd_arch(0x03400004u) == 13);
    assert(cug_gmd_release(0x03400004u) == 0);
    assert(cug_gmd_revision(0x03400004u) == 4);
    assert(!cug_gmd_value_valid(0));
    assert(!cug_gmd_value_valid(0xffffffffu));
    assert(!cug_gmd_value_valid(0x003fffffu));
    return 0;
}
