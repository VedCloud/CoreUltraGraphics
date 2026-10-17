"""Generate reviewable source overlay; never modifies the upstream snapshot or USB EFI."""
from pathlib import Path
import difflib
import hashlib
import json

root = Path(__file__).resolve().parents[1]
up = root/'upstream/nullmoth/277a29bea10371a88c4c1fb104409060d31962e8/gpu-port/xkpi'
if not (up/'bsdcompat/src/nmx_misc.c').exists():
    up = root/'tooling/build-inputs/nvidia-macos-driver-277a29bea10371a88c4c1fb104409060d31962e8/gpu-port/xkpi'
dest = root/'port/nullmoth-candidate'
records = []


def replace(text, old, new):
    assert text.count(old) == 1, old[:100]
    return text.replace(old, new)


original = (up/'override/src/nmx_fb_bridge.c').read_text()
source = replace(original, '#include "nmx_port.h"', '#include "nmx_port.h"\n#include "nmx_i915_bridge.h"')
source = replace(source, '    int mapped;', '    int mapped;\n    struct nmx_i915_mapping *intel_mapping;')
source = replace(source, '    if (fb->mapped)\n        drm_client_buffer_vunmap(fb->buffer);',
                 '    if (fb->intel_mapping)\n        nmx_i915_fb_unmap(fb->intel_mapping);\n    else if (fb->mapped)\n        drm_client_buffer_vunmap(fb->buffer);')
source = replace(source, '    err = -drm_client_buffer_vmap(fb->buffer, &fb->map);', '''    uint64_t size = (uint64_t)out->pitch * out->height;
    uint64_t base = 0;
    if (!size || size > UINT64_MAX - (PAGE_SIZE - 1)) {
        err = EOVERFLOW;
        goto fail;
    }
    if (!strcmp(drm->driver->name, "i915"))
        err = -nmx_i915_fb_map(fb->buffer, &fb->map, round_page(size),
                              &base, &fb->intel_mapping);
    else
        err = -drm_client_buffer_vmap(fb->buffer, &fb->map);''')
source = replace(source, '    uint64_t size = (uint64_t)out->pitch * out->height;\n    uint64_t base = nmx_xnu_kva_to_phys(va);\n    for (uint64_t off = PAGE_SIZE; off < size; off += PAGE_SIZE)',
'''    if (!fb->intel_mapping)
        base = nmx_xnu_kva_to_phys(va);
    /* Reject an existing i915 CPU mapping that does not address this aperture. */
    if (fb->intel_mapping && nmx_xnu_kva_to_phys(va) != base) {
        err = EFAULT;
        goto fail;
    }
    for (uint64_t off = PAGE_SIZE; off < size; off += PAGE_SIZE)''')
source = replace(source, '    memset(__DECONST(char *, va), 0, size);', '    iosys_map_memset(&fb->map, 0, 0, size);')
# drm_drv.h supplies the complete driver definition for driver-name dispatch.
source = replace(source, '#include <drm/drm_device.h>', '#include <drm/drm_device.h>\n#include <drm/drm_drv.h>')
source = replace(source, 'extern int amdgpu_sg_display;', '#ifndef NMX_INTEL_ONLY\nextern int amdgpu_sg_display;\n#endif')
source = replace(source, '    amdgpu_sg_display = 0;', '#ifndef NMX_INTEL_ONLY\n    amdgpu_sg_display = 0;\n#endif')
files = [('override/src/nmx_fb_bridge.c', original, source)]

original = (up/'xnu/nmx_kext.cpp').read_text()
source = replace(original, '#include "nmx_xnu.h"', '#include "nmx_xnu.h"\n#include "nmx_i915_bridge.h"')
source = replace(source, '    if (!g_started) {\n        int err = nmx_port_start();', '''    if (!g_started) {
        int guc = 0;
        if (PE_parse_boot_argn("nmxguc", &guc, sizeof(guc))) {
            int policy_error = nmx_i915_set_guc_mode(guc);
            if (policy_error) {
                IOLockUnlock(g_lock);
                IOLog("NullMoth GPU: invalid nmxguc=%d (expected 0..3)\\n", guc);
                IOService::stop(provider);
                return false;
            }
            IOLog("NullMoth GPU: explicit i915 enable_guc=%d before port initialization\\n", guc);
        }
        int err = nmx_port_start();''')
claim = '''    /* NMXAccel (the Metal accelerator for this GPU) starts only on a device this driver has claimed; it declined while
       the claim was pending, so matching on the device runs again now that it is set */
    pci_->setProperty("nmxgpu-claimed", kOSBooleanTrue);
    pci_->registerService();
    /* light the outputs and hand them to macOS; without it the device still renders, with no screen of its own */
    fb_ = nmx_fb_publish(this, dev_);'''
source = replace(source, claim, '''    fb_ = nmx_fb_publish(this, dev_);
    if (fb_ == nullptr) {
        setProperty("nullmoth-gpu-state", "attached: framebuffer unavailable");
        nmx_marker_write(false);
        IOLog("NullMoth GPU: no framebuffer; withholding the accelerator claim\\n");
        attach_ = -1;
        return;
    }
    /* Start accelerator matching only after the framebuffer exists. */
    pci_->setProperty("nmxgpu-claimed", kOSBooleanTrue);
    pci_->registerService();''')
files.append(('xnu/nmx_kext.cpp', original, source))

# Match the pinned kernel SDK's strnstr prototype without changing its search.
original = (up/'bsdcompat/src/nmx_misc.c').read_text()
source = replace(original, 'char *strnstr(const char *s, const char *find, size_t slen)',
                 'char *strnstr(char *s, const char *find, size_t slen)')
files.append(('bsdcompat/src/nmx_misc.c', original, source))
original = (up/'xnu/nmx_platform.cpp').read_text()
# The path is NUL terminated. Match the old bounded search without relying on
# kernel-SDK-specific const qualifiers or unavailable user-space declarations.
source = replace(original, '#include "nmx_xnu.h"', '''#include "nmx_xnu.h"
static bool nmx_path_has_parent_marker(const char *p)
{
    for (; *p; ++p)
        if (p[0] == '.' && p[1] == '.')
            return true;
    return false;
}''')
source = replace(source, 'strnstr(name, "..", strlen(name) + 1) != nullptr', 'nmx_path_has_parent_marker(name)')
files.append(('xnu/nmx_platform.cpp', original, source))

patch = ''
for relative, original, source in files:
    output = dest/Path(relative).name
    output.write_text(source, newline='\n')
    patch += ''.join(difflib.unified_diff(original.splitlines(True), source.splitlines(True),
                       fromfile='a/gpu-port/xkpi/'+relative, tofile='b/gpu-port/xkpi/'+relative))
    records.append(dict(path=relative, original_sha256=hashlib.sha256(original.encode()).hexdigest(),
                        candidate_sha256=hashlib.sha256(source.encode()).hexdigest()))
(dest/'0003-intel-guc-and-scanout-integration.patch').write_text(patch, newline='\n')
(dest/'bridge-overlay.json').write_text(json.dumps(dict(base_commit='277a29bea10371a88c4c1fb104409060d31962e8',
                    files=records, linked_into_kext=False, installed=False), indent=2)+'\n')
print(json.dumps(records, indent=2))
