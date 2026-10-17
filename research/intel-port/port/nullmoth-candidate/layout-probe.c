/* SPDX-License-Identifier: MIT */
#include <stddef.h>
#include <drm/drm_client.h>
#include "i915_drv.h"
#include "i915_vma.h"
/* Read-only object-file constants for detecting incompatible source builds. */
const unsigned long nmx_layout_params = offsetof(struct drm_i915_private, params);
const unsigned long nmx_layout_guc = offsetof(struct i915_params, enable_guc);
const unsigned long nmx_layout_gem_funcs = offsetof(struct drm_gem_object, funcs);
const unsigned long nmx_layout_i915_runtime_pm = offsetof(struct drm_i915_private, runtime_pm);
const unsigned long nmx_layout_vma_vm = offsetof(struct i915_vma, vm);
const unsigned long nmx_layout_vma_obj = offsetof(struct i915_vma, obj);
