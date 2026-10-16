/* Offline packet encoder; no OS APIs or GPU access. See docs/PORTING.md. */
#ifndef INTEL_MACOS_MI_BATCH_H
#define INTEL_MACOS_MI_BATCH_H
#include <stdint.h>
#include <stddef.h>

/* Output is six host-endian dwords; intended target is little-endian x86_64.
 * Returns 0 without modifying output on invalid inputs; returns 1 on success.
 * GPU ownership, mapping, coherency, engine state and submission are external.
 */
static inline int im_store_dword_batch(uint64_t gpu_address, uint32_t value,
                                      uint32_t *output, size_t capacity_dwords)
{
    if (!output || capacity_dwords < 6 || (gpu_address & 3) ||
        gpu_address >= (UINT64_C(1) << 48))
        return 0;
    output[0] = (UINT32_C(32) << 23) | 2;
    output[1] = (uint32_t)gpu_address;
    output[2] = (uint32_t)(gpu_address >> 32);
    output[3] = value;
    output[4] = UINT32_C(10) << 23;
    output[5] = 0;
    return 1;
}
#endif
