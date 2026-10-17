/* SPDX-License-Identifier: MIT
 * Intel-specific CPU scanout mapping for the NMX DRM bridge.
 * Uses the public i915 GGTT APIs; no structure offsets or binary trampolines.
 */
#include <linux/slab.h>
#include <linux/iosys-map.h>
#include <drm/drm_client.h>
#include <drm/drm_drv.h>
#include <drm/drm_framebuffer.h>
#include "i915_drv.h"
#include "i915_gem.h"
#include "i915_params.h"
#include "i915_vma.h"
#include "gem/i915_gem_object.h"
#include "gt/intel_gt.h"
#include "i915_gem_ww.h"
#include "nmx_i915_bridge.h"
#include "nmx_scanout_range.h"

struct nmx_i915_mapping {
    struct drm_i915_private *i915;
    struct i915_vma *vma;
    intel_wakeref_t wakeref;
};

int nmx_i915_set_guc_mode(int mode)
{
    if (mode < 0 || mode > ENABLE_GUC_MASK)
        return -EINVAL;
    i915_modparams.enable_guc = mode;
    return 0;
}

int nmx_i915_fb_map(struct drm_client_buffer *buffer, struct iosys_map *map,
                    uint64_t size, uint64_t *physical, struct nmx_i915_mapping **out)
{
    struct nmx_i915_mapping *mapping;
    struct drm_i915_private *i915;
    struct drm_i915_gem_object *obj;
    struct i915_gem_ww_ctx ww;
    struct i915_vma *vma = NULL;
    void __iomem *address;
    uint64_t base = 0;
    int err;

    *physical = 0;
    *out = NULL;
    iosys_map_clear(map);
    if (!buffer || !buffer->gem || !buffer->fb || !buffer->client ||
        !buffer->client->dev || !buffer->client->dev->driver ||
        strcmp(buffer->client->dev->driver->name, "i915"))
        return -ENODEV;
    i915 = to_i915(buffer->client->dev);
    obj = to_intel_bo(buffer->gem);
    if (intel_gt_is_wedged(to_gt(i915)))
        return -EIO;
    /* This bridge describes an integrated-GPU aperture, not discrete LMEM. */
    if (HAS_LMEM(i915) || buffer->fb->modifier != DRM_FORMAT_MOD_LINEAR ||
        !size || size > obj->base.size)
        return -EINVAL;
    mapping = kzalloc(sizeof(*mapping), GFP_KERNEL);
    if (!mapping)
        return -ENOMEM;
    mapping->i915 = i915;
    /* WindowServer writes without entering our driver: keep aperture access awake. */
    mapping->wakeref = intel_runtime_pm_get(&i915->runtime_pm);
    i915_gem_ww_ctx_init(&ww, true);
retry:
    err = i915_gem_object_lock(obj, &ww);
    if (err)
        goto retry_or_fail;
    vma = i915_gem_object_ggtt_pin_ww(obj, &ww, NULL, 0, 0, PIN_MAPPABLE);
    if (IS_ERR(vma)) {
        err = PTR_ERR(vma);
        vma = NULL;
        goto retry_or_fail;
    }
    /* Fail before exposing memory if this driver cannot provide a real aperture map. */
    if (!i915_vma_is_map_and_fenceable(vma)) {
        err = -ENXIO;
        goto unpin;
    }
    {
        struct i915_ggtt *ggtt = i915_vm_to_ggtt(vma->vm);
        if (!nmx_scanout_range(ggtt->gmadr.start, resource_size(&ggtt->gmadr),
                               ggtt->mappable_end, i915_ggtt_offset(vma),
                               i915_vma_size(vma), obj->base.size, size, &base)) {
            err = -ERANGE;
            goto unpin;
        }
    }
    address = i915_vma_pin_iomap(vma);
    if (IS_ERR(address)) {
        err = PTR_ERR(address);
        goto unpin;
    }
    mapping->vma = i915_vma_get(vma);
    /* drm_client_framebuffer_delete must follow our unmap, so obj stays referenced. */
    iosys_map_set_vaddr_iomem(map, address);
    i915_gem_ww_ctx_fini(&ww);
    *physical = base;
    *out = mapping;
    return 0;
unpin:
    i915_vma_unpin(vma);
    vma = NULL;
retry_or_fail:
    if (err == -EDEADLK) {
        err = i915_gem_ww_ctx_backoff(&ww);
        if (!err)
            goto retry;
    }
    i915_gem_ww_ctx_fini(&ww);
    intel_runtime_pm_put(&i915->runtime_pm, mapping->wakeref);
    kfree(mapping);
    return err;
}

void nmx_i915_fb_unmap(struct nmx_i915_mapping *mapping)
{
    if (!mapping)
        return;
    i915_vma_unpin_iomap(mapping->vma);
    i915_vma_unpin(mapping->vma);
    i915_vma_put(mapping->vma);
    intel_runtime_pm_put(&mapping->i915->runtime_pm, mapping->wakeref);
    kfree(mapping);
}
