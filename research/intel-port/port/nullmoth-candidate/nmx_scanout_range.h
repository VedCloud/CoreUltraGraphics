/* SPDX-License-Identifier: MIT */
#ifndef NMX_SCANOUT_RANGE_H
#define NMX_SCANOUT_RANGE_H
#include <stdint.h>
/* A physical range must describe the entire rounded framebuffer in the aperture.
 * Use subtraction tests so adversarial/invalid sizes cannot wrap at 64 bits. */
static inline int nmx_scanout_range(uint64_t aperture, uint64_t aperture_size,
                                    uint64_t mappable, uint64_t offset,
                                    uint64_t vma_size, uint64_t object_size,
                                    uint64_t required, uint64_t *physical)
{
    *physical = 0;
    if (!aperture || (aperture & 4095) || !aperture_size || !mappable || !required ||
        (required & 4095) || (offset & 4095) || required > object_size ||
        required > vma_size || offset > aperture_size ||
        required > aperture_size - offset || offset > mappable ||
        required > mappable - offset || aperture > UINT64_MAX - offset ||
        aperture + offset > UINT64_MAX - (required - 1))
        return 0;
    *physical = aperture + offset;
    return 1;
}
#endif
