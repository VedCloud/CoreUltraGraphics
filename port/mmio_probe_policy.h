/* Original bounded read policy. Register facts: Linux v6.12 xe_gt_regs.h. */
#ifndef CUG_MMIO_PROBE_POLICY_H
#define CUG_MMIO_PROBE_POLICY_H
#define CUG_GRAPHICS_GMD_ID 0x00000d8cu
#define CUG_MEDIA_GMD_ID    0x00380d8cu
static inline int cug_probe_read_allowed(unsigned int offset, unsigned long long length)
{
    if (offset != CUG_GRAPHICS_GMD_ID && offset != CUG_MEDIA_GMD_ID) return 0;
    return length >= 4u && (unsigned long long)offset <= length - 4u;
}
static inline unsigned int cug_gmd_arch(unsigned int raw) { return (raw >> 22) & 0x3ffu; }
static inline unsigned int cug_gmd_release(unsigned int raw) { return (raw >> 14) & 0xffu; }
static inline unsigned int cug_gmd_revision(unsigned int raw) { return raw & 0x3fu; }
static inline int cug_gmd_value_valid(unsigned int raw)
{
    return raw != 0u && raw != 0xffffffffu && cug_gmd_arch(raw) != 0u;
}
#endif
