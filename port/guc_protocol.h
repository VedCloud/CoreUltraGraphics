/* GuC host-message encoding from the public Linux Xe HXG/CTB ABI.
 * No MMIO, firmware upload, GPU memory allocation or submission occurs here.
 */
#ifndef CORE_ULTRA_GUC_PROTOCOL_H
#define CORE_ULTRA_GUC_PROTOCOL_H
#include <stdint.h>
#include <stddef.h>

struct cug_guc_ctb_descriptor {
    uint32_t head, tail, status, reserved[13];
};
#if defined(__cplusplus)
static_assert(sizeof(struct cug_guc_ctb_descriptor) == 64, "GuC descriptor must be 64 bytes");
#else
_Static_assert(sizeof(struct cug_guc_ctb_descriptor) == 64, "GuC descriptor must be 64 bytes");
#endif

/* Four-dword MMIO HXG request, for transport by a future hardware layer.
 * value is an encoded value/GPU address, never implicitly a CPU physical address.
 * Invalid input leaves output untouched. Capacity is measured in dwords.
 */
static inline int cug_guc_self_config(uint16_t key, uint64_t value,
                                     unsigned value_dwords, uint32_t *output,
                                     size_t capacity)
{
    if (!output || capacity < 4 || (value_dwords != 1 && value_dwords != 2) ||
        (value_dwords == 1 && value > UINT32_MAX))
        return 0;
    output[0] = UINT32_C(0x0508);
    output[1] = ((uint32_t)key << 16) | value_dwords;
    output[2] = (uint32_t)value;
    output[3] = value_dwords == 2 ? (uint32_t)(value >> 32) : 0;
    return 1;
}

static inline int cug_guc_ctb_control(unsigned enabled, uint32_t *output, size_t capacity)
{
    if (!output || capacity < 2 || enabled > 1)
        return 0;
    output[0] = UINT32_C(0x4509);
    output[1] = enabled;
    return 1;
}
#endif
