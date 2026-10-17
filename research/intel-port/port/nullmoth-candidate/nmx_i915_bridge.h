/* SPDX-License-Identifier: MIT */
#ifndef NMX_I915_BRIDGE_H
#define NMX_I915_BRIDGE_H
#include <stdint.h>
struct drm_client_buffer;
struct iosys_map;
struct nmx_i915_mapping;
#ifdef __cplusplus
extern "C" {
#endif
/* Call before nmx_port_start; negative errno on invalid policy. */
int nmx_i915_set_guc_mode(int mode);
/* Negative Linux errno; outputs remain zero on failure. */
int nmx_i915_fb_map(struct drm_client_buffer *, struct iosys_map *,
                    uint64_t size, uint64_t *physical, struct nmx_i915_mapping **);
void nmx_i915_fb_unmap(struct nmx_i915_mapping *);
#ifdef __cplusplus
}
#endif
#endif
