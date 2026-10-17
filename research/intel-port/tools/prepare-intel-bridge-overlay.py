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
# Boundaries before PCI matching were silent in the first source-build boot.
# These messages describe entry/return only; none claims firmware or GPU success.
source = replace(source, '    bool pm_;', '''    bool pm_;
    unsigned int attach_thread_stage_; /* atomic diagnostic checkpoints only */''')
source = replace(source, '    attach_ = 0;\n    retain();', '''    attach_ = 0;
    __atomic_store_n(&attach_thread_stage_, 0u, __ATOMIC_RELEASE);
    retain();''')
source = replace(source, '    self->attachNow();', '''    /* No logging, registry operation or allocation before this checkpoint. */
    __atomic_store_n(&self->attach_thread_stage_, 1u, __ATOMIC_RELEASE);
    self->attachNow();''')
source = replace(source, '        g_started = true;', '''        IOLog("NullMoth GPU: stage port-start returned successfully\\n");
        g_started = true;''')
source = replace(source, '    IOLockUnlock(g_lock);\n\n    /*', '''    IOLockUnlock(g_lock);
    IOLog("NullMoth GPU: stage start lock released\\n");

    /*''')
source = replace(source, '    thread_t t = THREAD_NULL;', '''    IOLog("NullMoth GPU: stage creating attach thread\\n");
    thread_t t = THREAD_NULL;''')
source = replace(source, '    thread_deallocate(t);', '''    thread_deallocate(t);
    IOLog("NullMoth GPU: stage attach thread created\\n");
    /* Yield briefly to observe entry without holding g_lock. Do not treat a
       late worker as a failure or cancel it: this is not an attach timeout. */
    for (unsigned int i = 0; i < 100; ++i) {
        if (__atomic_load_n(&attach_thread_stage_, __ATOMIC_ACQUIRE) >= 3u)
            break;
        IOSleep(10);
    }
    IOLog("NullMoth GPU: worker checkpoint=%u (0=not entered, 1=before log, "
          "2=before registry, 3=firmware wait, 4=wait returned)\\n",
          __atomic_load_n(&attach_thread_stage_, __ATOMIC_ACQUIRE));''')
source = replace(source, '    int err = nmx_xnu_wait_firmware_root(300);', '''    IOLog("NullMoth GPU: stage attach thread entered; waiting for firmware root\\n");
    __atomic_store_n(&attach_thread_stage_, 2u, __ATOMIC_RELEASE);
    setProperty("nullmoth-gpu-state", "waiting: firmware root");
    __atomic_store_n(&attach_thread_stage_, 3u, __ATOMIC_RELEASE);
    int err = nmx_xnu_wait_firmware_root(300);
    __atomic_store_n(&attach_thread_stage_, 4u, __ATOMIC_RELEASE);
    IOLog("NullMoth GPU: stage firmware-root wait returned %d\\n", err);''')
source = replace(source, '    if (nmx_marker_set()) {', '''    IOLog("NullMoth GPU: stage reading attach guard\\n");
    if (nmx_marker_set()) {''')
source = replace(source, '    nmx_marker_write(true);\n    dev_ = nmx_port_attach(pci_);', '''    IOLog("NullMoth GPU: stage writing attach guard\\n");
    nmx_marker_write(true);
    IOLog("NullMoth GPU: stage entering PCI driver attachment\\n");
    setProperty("nullmoth-gpu-state", "attaching: PCI driver");
    dev_ = nmx_port_attach(pci_);
    IOLog("NullMoth GPU: stage PCI driver attachment returned %s\\n",
          dev_ ? "device" : "null");''')
# Identify the loaded image before port startup, bypassing IOLog's os_log path.
source = replace(source, '#include <kern/thread.h>', '#include <kern/thread.h>\n#include <i386/machine_routines.h>\n#include <libkern/libkern.h>')
source = replace(source, 'bool NMXGPU::start(IOService *provider)\n{', '''bool NMXGPU::start(IOService *provider)
{
    printf("CUG-HANDOFF-20261017-B1: start entered IF=%d\\n", ml_get_interrupts_enabled());''')
source = replace(source, '        int err = nmx_port_start();', '''        printf("CUG-B1: before port-start IF=%d\\n", ml_get_interrupts_enabled());
        int err = nmx_port_start();
        printf("CUG-B1: after port-start error=%d IF=%d\\n", err, ml_get_interrupts_enabled());''')
begin = source.index('    /* Yield briefly to observe entry')
end = source.index('    return true;\n}', begin)
source = source[:begin] + '''    /* Never wait for the worker while IOKit is still inside start(). */
    printf("CUG-B1: start returning checkpoint=%u IF=%d\\n",
           __atomic_load_n(&attach_thread_stage_, __ATOMIC_ACQUIRE),
           ml_get_interrupts_enabled());
''' + source[end:]
source = source.replace('IOLog(', 'printf(')
# B2: no port initialization in the IOKit matching callback. Keep a device
# reference/count until the worker is joined, even when runtime startup fails.
source = replace(source, '    unsigned int attach_thread_stage_; /* atomic diagnostic checkpoints only */',
    r'''    unsigned int attach_thread_stage_; /* atomic diagnostic checkpoints only */
    unsigned int attach_thread_done_;
    unsigned int attach_cancel_;''')
start = source.index('    IOLockLock(g_lock);', source.index('bool NMXGPU::start('))
end = source.index('    /*\n     * amdgpu', start)
port_start = source[start:end]
port_start = port_start[:port_start.index('    g_devices++;')]
port_start = port_start.replace('                IOService::stop(provider);\n                return false;',
    '                nmx_marker_write(false);\n                attach_ = -1;\n                return;')
port_start = port_start.replace('            IOService::stop(provider);\n            return false;',
    '            nmx_marker_write(false);\n            attach_ = -1;\n            return;')
port_start += '    IOLockUnlock(g_lock);\n'
source = source[:start] + r'''    /* Count the service before scheduling: an unstarted runtime is not unloadable
       while a worker still holds code or the global lock. */
    IOLockLock(g_lock);
    g_devices++;
    IOLockUnlock(g_lock);

''' + source[end:]
source = replace(source, 'CUG-HANDOFF-20261017-B1: start entered IF=%d',
    'CUG-HANDOFF-20261017-B2: start entered IF=%d')
source = replace(source, '    __atomic_store_n(&attach_thread_stage_, 0u, __ATOMIC_RELEASE);',
    r'''    __atomic_store_n(&attach_thread_stage_, 0u, __ATOMIC_RELEASE);
    __atomic_store_n(&attach_thread_done_, 0u, __ATOMIC_RELEASE);
    __atomic_store_n(&attach_cancel_, 0u, __ATOMIC_RELEASE);
    setProperty("nullmoth-gpu-build", "CUG-HANDOFF-20261017-B2");
    setProperty("nullmoth-gpu-state", "queued: attach worker");''')
source = replace(source, '    printf("NullMoth GPU: stage creating attach thread\\n");\n', '')
source = replace(source, r'''        printf("NullMoth GPU: could not start the attach thread\n");
        attach_ = -1;
        release();
        return true;''', r'''        attach_ = -1;
        __atomic_store_n(&attach_thread_done_, 1u, __ATOMIC_RELEASE);
        release();
        IOLockLock(g_lock);
        g_devices--;
        IOLockUnlock(g_lock);
        IOService::stop(provider);
        return false;''')
begin = source.index('    printf("NullMoth GPU: stage attach thread created')
end = source.index('    return true;\n}', begin)
source = source[:begin] + '    /* Return without waiting for port startup, firmware or the worker. */\n' + source[end:]
source = replace(source, '    self->attachNow();\n    self->release();', r'''    self->attachNow();
    /* Release publishes all dev_/fb_/pm_ writes to stop(), not merely attach_. */
    __atomic_store_n(&self->attach_thread_done_, 1u, __ATOMIC_RELEASE);
    self->release();''')
source = replace(source, '    printf("NullMoth GPU: stage attach thread entered; waiting for firmware root\\n");',
    r'''    if (__atomic_load_n(&attach_cancel_, __ATOMIC_ACQUIRE)) {
        attach_ = -1;
        return;
    }
    printf("CUG-B2: worker entered; waiting for firmware root\n");''')
source = replace(source, '    if (err) {\n        printf("NullMoth GPU: the firmware folder never appeared',
    '    if (err || __atomic_load_n(&attach_cancel_, __ATOMIC_ACQUIRE)) {\n        printf("NullMoth GPU: firmware wait failed or attachment cancelled')
source = replace(source, '    nmx_marker_write(true);\n    printf("NullMoth GPU: stage entering PCI driver attachment\\n");',
    '    nmx_marker_write(true);\n    setProperty("nullmoth-gpu-state", "initializing: port runtime");\n' +
    port_start.replace('CUG-B1:', 'CUG-B2:') + r'''    if (__atomic_load_n(&attach_cancel_, __ATOMIC_ACQUIRE)) {
        nmx_marker_write(false);
        attach_ = -1;
        return;
    }
    printf("NullMoth GPU: stage entering PCI driver attachment\n");''')
source = replace(source, r'''    /* an attach still running on its thread finishes first (it holds a reference on this object meanwhile) */
    for (int i = 0; attach_ == 0 && i < 6000; i++)
        IOSleep(100);''', r'''    /* A timeout cannot grant ownership of resources still used by a worker.
       Cancellation prevents a queued worker from attaching; an in-flight driver
       call must finish before any framebuffer, PM or PCI resource is detached. */
    __atomic_store_n(&attach_cancel_, 1u, __ATOMIC_RELEASE);
    while (!__atomic_load_n(&attach_thread_done_, __ATOMIC_ACQUIRE))
        IOSleep(100);''')
# The count protects workers before g_started becomes true, too.
source = replace(source, r'''    IOLockLock(g_lock);
    if (g_started) {
        if (g_devices > 0 || nmx_port_busy() > 0) {''', r'''    IOLockLock(g_lock);
    if (g_devices > 0) {
        IOLockUnlock(g_lock);
        return KERN_FAILURE;
    }
    if (g_started) {
        if (nmx_port_busy() > 0) {''')

# B3 records every external-call boundary in start, and offers a worker-only
# diagnostic mode that leaves the GPU hardware and display ownership untouched.
source = source.replace('CUG-HANDOFF-20261017-B2', 'CUG-HANDOFF-20261017-B3')
source = replace(source, r'''    IOPCIDevice *pci = OSDynamicCast(IOPCIDevice, provider);
    if (pci == nullptr || g_lock == nullptr || !IOService::start(provider))
        return false;''', r'''    printf("CUG-B3 S01: before provider cast\n");
    IOPCIDevice *pci = OSDynamicCast(IOPCIDevice, provider);
    printf("CUG-B3 S02: cast=%d lock=%d\n", pci != nullptr, g_lock != nullptr);
    if (pci == nullptr || g_lock == nullptr)
        return false;
    printf("CUG-B3 S03: before base start\n");
    bool base_started = IOService::start(provider);
    printf("CUG-B3 S04: base returned %d\n", base_started);
    if (!base_started)
        return false;''')
source = replace(source, r'''    IOLockLock(g_lock);
    g_devices++;
    IOLockUnlock(g_lock);''', r'''    printf("CUG-B3 S05: before device-count lock\n");
    IOLockLock(g_lock);
    printf("CUG-B3 S06: device-count lock acquired\n");
    g_devices++;
    IOLockUnlock(g_lock);
    printf("CUG-B3 S07: device-count lock released\n");''')
source = replace(source, r'''    setProperty("nullmoth-gpu-build", "CUG-HANDOFF-20261017-B3");
    setProperty("nullmoth-gpu-state", "queued: attach worker");
    retain();''', r'''    printf("CUG-B3 S08: before build property\n");
    setProperty("nullmoth-gpu-build", "CUG-HANDOFF-20261017-B3");
    printf("CUG-B3 S09: build property returned; before state property\n");
    setProperty("nullmoth-gpu-state", "queued: attach worker");
    printf("CUG-B3 S10: state property returned; before retain\n");
    retain();
    printf("CUG-B3 S11: retain returned\n");''')
source = replace(source, '    if (kernel_thread_start(&NMXGPU::attachThread, this, &t) != KERN_SUCCESS) {',
    r'''    printf("CUG-B3 S12: before kernel_thread_start\n");
    kern_return_t thread_result = kernel_thread_start(&NMXGPU::attachThread, this, &t);
    printf("CUG-B3 S13: kernel_thread_start returned %d\n", thread_result);
    if (thread_result != KERN_SUCCESS) {''')
source = replace(source, r'''    thread_deallocate(t);
    /* Return without waiting for port startup, firmware or the worker. */
    return true;''', r'''    printf("CUG-B3 S14: before thread reference release\n");
    thread_deallocate(t);
    printf("CUG-B3 S15: start returning; worker checkpoint=%u\n",
           __atomic_load_n(&attach_thread_stage_, __ATOMIC_ACQUIRE));
    return true;''')
source = replace(source, '    self->attachNow();', r'''    printf("CUG-B3 W01: worker callback entered\n");
    int diagnostic = 0;
    if (PE_parse_boot_argn("nmxdiag", &diagnostic, sizeof(diagnostic)) && diagnostic == 1) {
        self->setProperty("nullmoth-gpu-state", "diagnostic: worker ran; hardware untouched");
        __atomic_store_n(&self->attach_thread_stage_, 5u, __ATOMIC_RELEASE);
        self->attach_ = -1;
        printf("CUG-B3 W02: worker-only diagnostic complete; no port or display initialization\n");
    } else {
        self->attachNow();
    }''')

files.append(('xnu/nmx_kext.cpp', original, source))

# Expose each boundary inside the formerly silent synchronous port startup.
original = (up/'bsdcompat/src/nmx_port.c').read_text()
begin = original.index('#define STEP(call)')
end = original.index('    stage = 0;', begin)
source = original[:begin] + '''#define STEP(call) do { printf("CUG-B1: port entering %s\\n", #call); \\
    err = (call); printf("CUG-B1: port returned %s error=%d\\n", #call, err); \\
    if (err != 0) { nmx_port_stop(); return err; } stage++; } while (0)
''' + original[end:]
files.append(('bsdcompat/src/nmx_port.c', original, source))

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
