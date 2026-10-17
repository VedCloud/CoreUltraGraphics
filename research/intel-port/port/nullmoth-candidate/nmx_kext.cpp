/*
 * The kext: one IOService per AMD or Intel GPU it is allowed to drive (amdgpu and i915 share one DRM core and one
 * port layer here). Compiled with Apple's headers only; everything else is reached through nmx_port.h.
 *
 * Opt-in only, per vendor. The service matches every AMD and Intel display-class device but declines in probe()
 * unless the user asked for that vendor: boot argument nmxamd=1 / nmxintel=1, or the device property
 * "nullmoth-gpu" (set through the bootloader's DeviceProperties). Without that, the device keeps whatever driver macOS
 * gives it. Taking a GPU that is lighting the boot display resets its display engine, so the opt-in is per user,
 * never a default.
 *
 * The port (the FreeBSD/Linux layer and the AMD driver) starts with the first device and stops when the kext
 * unloads; unloading is refused while any process still has a GPU device node open.
 */
#include <IOKit/IOService.h>
#include <IOKit/IOLib.h>
#include <IOKit/IOLocks.h>
#include <IOKit/IONVRAM.h>
#include <IOKit/pci/IOPCIDevice.h>
#include <libkern/c++/OSBoolean.h>
#include <libkern/c++/OSData.h>
#include <mach/kmod.h>
#include <pexpert/pexpert.h>
#include <kern/thread.h>
#include <i386/machine_routines.h>
#include <libkern/libkern.h>
#include "nmx_port.h"
#include "nmx_xnu.h"
#include "nmx_i915_bridge.h"

#define AMD_VENDOR 0x1002
#define INTEL_VENDOR 0x8086

/* the display bridge (nmx_fb.cpp) */
IOService *nmx_fb_publish(IOService *gpu, void *dev);
void nmx_fb_unpublish(IOService *fb, IOService *gpu, void *dev);

class NMXGPU : public IOService {
    OSDeclareDefaultStructors(NMXGPU)
    void *dev_;
    IOService *fb_;
    IOPCIDevice *pci_;
    volatile int attach_;   /* 0 = attach pending on its thread, 1 = attached, -1 = not attached */
    bool pm_;
    unsigned int attach_thread_stage_; /* atomic diagnostic checkpoints only */
    unsigned int attach_thread_done_;
    unsigned int attach_cancel_;
    static void attachThread(void *arg, wait_result_t);
    void attachNow();
    int startRuntime();
public:
    IOService *probe(IOService *provider, SInt32 *score) override;
    bool start(IOService *provider) override;
    void stop(IOService *provider) override;
    IOReturn setPowerState(unsigned long state, IOService *device) override;
    void systemWillShutdown(IOOptionBits spec) override;
};
OSDefineMetaClassAndStructors(NMXGPU, IOService)

static IOLock *g_lock;
static bool g_started;
static int g_devices;

static bool opted_in(IOPCIDevice *pci, uint16_t vendor)
{
    int v = 0;
    /* the boot picker's "Start once without NVIDIA driver" entry (-nvoff) parks every NullMoth GPU driver for that start */
    if (PE_parse_boot_argn("-nvoff", &v, sizeof(v)))
        return false;
    if (PE_parse_boot_argn(vendor == AMD_VENDOR ? "nmxamd" : "nmxintel", &v, sizeof(v)) && v != 0)
        return true;
    OSObject *p = pci->getProperty("nullmoth-gpu");
    if (OSBoolean *b = OSDynamicCast(OSBoolean, p))
        return b->isTrue();
    if (OSData *d = OSDynamicCast(OSData, p))
        return d->getLength() > 0 && ((const uint8_t *)d->getBytesNoCopy())[0] != 0;
    return false;
}

IOService *NMXGPU::probe(IOService *provider, SInt32 *score)
{
    IOPCIDevice *pci = OSDynamicCast(IOPCIDevice, provider);
    uint16_t vendor = pci ? pci->configRead16(kIOPCIConfigVendorID) : 0;
    if (vendor != AMD_VENDOR && vendor != INTEL_VENDOR)
        return nullptr;
    if (!opted_in(pci, vendor))
        return nullptr;     /* not asked for: leave the device to macOS */
    return IOService::probe(provider, score);
}

bool NMXGPU::start(IOService *provider)
{
    printf("CUG-HANDOFF-20261017-B4: start entered IF=%d\n", ml_get_interrupts_enabled());
    printf("CUG-B4 S01: before provider cast\n");
    IOPCIDevice *pci = OSDynamicCast(IOPCIDevice, provider);
    printf("CUG-B4 S02: cast=%d lock=%d\n", pci != nullptr, g_lock != nullptr);
    if (pci == nullptr || g_lock == nullptr)
        return false;
    printf("CUG-B4 S03: before base start\n");
    bool base_started = IOService::start(provider);
    printf("CUG-B4 S04: base returned %d\n", base_started);
    if (!base_started)
        return false;
    /* Count the service before scheduling: an unstarted runtime is not unloadable
       while a worker still holds code or the global lock. */
    printf("CUG-B4 S05: before device-count lock\n");
    IOLockLock(g_lock);
    printf("CUG-B4 S06: device-count lock acquired\n");
    g_devices++;
    IOLockUnlock(g_lock);
    printf("CUG-B4 S07: device-count lock released\n");

    /*
     * amdgpu, i915 and xe load firmware while they attach. During boot matching that read would come before the root and
     * Data volumes are mounted, and mounting waits for matching to settle: the Mac would stop at the logo (seen with the
     * NPU kext on the same layer, 10-11). The attach runs on its own thread once the firmware folder exists; the firmware
     * framebuffer keeps the screen until then.
     */
    pci_ = pci;
    dev_ = nullptr;
    fb_ = nullptr;
    pm_ = false;
    attach_ = 0;
    __atomic_store_n(&attach_thread_stage_, 0u, __ATOMIC_RELEASE);
    __atomic_store_n(&attach_thread_done_, 0u, __ATOMIC_RELEASE);
    __atomic_store_n(&attach_cancel_, 0u, __ATOMIC_RELEASE);
    printf("CUG-B4 S08: before build property\n");
    setProperty("nullmoth-gpu-build", "CUG-HANDOFF-20261017-B4");
    printf("CUG-B4 S09: build property returned; before state property\n");
    setProperty("nullmoth-gpu-state", "queued: attach worker");
    printf("CUG-B4 S10: state property returned; before retain\n");
    retain();
    printf("CUG-B4 S11: retain returned\n");
    thread_t t = THREAD_NULL;
    printf("CUG-B4 S12: before kernel_thread_start\n");
    kern_return_t thread_result = kernel_thread_start(&NMXGPU::attachThread, this, &t);
    printf("CUG-B4 S13: kernel_thread_start returned %d\n", thread_result);
    if (thread_result != KERN_SUCCESS) {
        attach_ = -1;
        __atomic_store_n(&attach_thread_done_, 1u, __ATOMIC_RELEASE);
        release();
        IOLockLock(g_lock);
        g_devices--;
        IOLockUnlock(g_lock);
        IOService::stop(provider);
        return false;
    }
    printf("CUG-B4 S14: before thread reference release\n");
    thread_deallocate(t);
    printf("CUG-B4 S15: start returning; worker checkpoint=%u\n",
           __atomic_load_n(&attach_thread_stage_, __ATOMIC_ACQUIRE));
    return true;
}

void NMXGPU::attachThread(void *arg, wait_result_t)
{
    NMXGPU *self = (NMXGPU *)arg;
    /* No logging, registry operation or allocation before this checkpoint. */
    __atomic_store_n(&self->attach_thread_stage_, 1u, __ATOMIC_RELEASE);
    printf("CUG-B4 W01: worker callback entered\n");
    int diagnostic = 0;
    if (PE_parse_boot_argn("nmxdiag", &diagnostic, sizeof(diagnostic)) && diagnostic == 1) {
        self->setProperty("nullmoth-gpu-state", "diagnostic: worker ran; hardware untouched");
        __atomic_store_n(&self->attach_thread_stage_, 5u, __ATOMIC_RELEASE);
        self->attach_ = -1;
        printf("CUG-B4 W02: worker-only diagnostic complete; no port or display initialization\n");
    } else if (diagnostic == 2) {
        printf("CUG-B4 W10: runtime-only diagnostic; before firmware-root wait\n");
        self->setProperty("nullmoth-gpu-state", "diagnostic: waiting for firmware root");
        int err = nmx_xnu_wait_firmware_root(300);
        printf("CUG-B4 W11: firmware-root wait returned %d\n", err);
        if (!err && !__atomic_load_n(&self->attach_cancel_, __ATOMIC_ACQUIRE)) {
            self->setProperty("nullmoth-gpu-state", "diagnostic: initializing port runtime");
            err = self->startRuntime();
            printf("CUG-B4 W12: port runtime returned %d; no PCI GPU attachment\n", err);
        } else if (!err) {
            err = -1;
        }
        self->setProperty("nullmoth-gpu-state", err ? "diagnostic: runtime failed or cancelled" :
                          "diagnostic: port runtime ready; GPU not attached");
        __atomic_store_n(&self->attach_thread_stage_, err ? 7u : 6u, __ATOMIC_RELEASE);
        self->attach_ = -1;
    } else {
        self->attachNow();
    }
    /* Release publishes all dev_/fb_/pm_ writes to stop(), not merely attach_. */
    __atomic_store_n(&self->attach_thread_done_, 1u, __ATOMIC_RELEASE);
    self->release();
}

/*
 * Boot guard, as in NMXNPU: the NPU kext on this layer panicked 7 s into every start until its boot argument was
 * removed from Linux. The attach, the modeset and the hand-over to macOS run between setting an NVRAM marker
 * and clearing it; a start that finds the marker still set follows an attach that never returned (a panic or a hang),
 * so this GPU stays with macOS and the driver says so. Turning the test driver off and on in the app clears it.
 */
static const char *const kAttachMarker = "nullmoth-gpu-attaching";

static IODTNVRAM *nmx_nvram()
{
    IORegistryEntry *e = IORegistryEntry::fromPath("/options", gIODTPlane);
    IODTNVRAM *n = OSDynamicCast(IODTNVRAM, e);
    if (n == nullptr && e != nullptr)
        e->release();
    return n;
}

static bool nmx_marker_set()
{
    IODTNVRAM *n = nmx_nvram();
    if (n == nullptr)
        return false;
    OSObject *v = n->copyProperty(kAttachMarker);
    bool set = v != nullptr;
    if (v)
        v->release();
    n->release();
    return set;
}

static void nmx_marker_write(bool on)
{
    IODTNVRAM *n = nmx_nvram();
    if (n == nullptr) {
        printf("NullMoth GPU: no NVRAM; the boot guard is off\n");
        return;
    }
    const OSSymbol *k = OSSymbol::withCString(kAttachMarker);
    if (k != nullptr) {
        if (on) {
            OSData *d = OSData::withBytes("1", 1);
            if (d == nullptr || !n->setProperty(k, d))
                printf("NullMoth GPU: could not set the boot guard\n");
            if (d)
                d->release();
        } else {
            n->removeProperty(k);
        }
        k->release();
    }
    n->sync();
    n->release();
}

void NMXGPU::attachNow()
{
    if (__atomic_load_n(&attach_cancel_, __ATOMIC_ACQUIRE)) {
        attach_ = -1;
        return;
    }
    printf("CUG-B4: worker entered; waiting for firmware root\n");
    __atomic_store_n(&attach_thread_stage_, 2u, __ATOMIC_RELEASE);
    setProperty("nullmoth-gpu-state", "waiting: firmware root");
    __atomic_store_n(&attach_thread_stage_, 3u, __ATOMIC_RELEASE);
    int err = nmx_xnu_wait_firmware_root(300);
    __atomic_store_n(&attach_thread_stage_, 4u, __ATOMIC_RELEASE);
    printf("NullMoth GPU: stage firmware-root wait returned %d\n", err);
    if (err || __atomic_load_n(&attach_cancel_, __ATOMIC_ACQUIRE)) {
        printf("NullMoth GPU: firmware wait failed or attachment cancelled (%d); this GPU stays with macOS\n", err);
        attach_ = -1;
        return;
    }
    printf("NullMoth GPU: stage reading attach guard\n");
    if (nmx_marker_set()) {
        printf("NullMoth GPU: the last attach of %04x:%04x never returned (the Mac stopped or restarted); this GPU stays "
              "with macOS. Send logs, then turn the test driver off and on to try again\n",
              pci_->configRead16(kIOPCIConfigVendorID), pci_->configRead16(kIOPCIConfigDeviceID));
        setProperty("nullmoth-gpu-state", "parked: the last attach never returned");
        attach_ = -1;
        return;
    }
    printf("NullMoth GPU: stage writing attach guard\n");
    nmx_marker_write(true);
    setProperty("nullmoth-gpu-state", "initializing: port runtime");
    int runtime_error = startRuntime();
    if (runtime_error) {
        nmx_marker_write(false);
        attach_ = -1;
        return;
    }
    if (__atomic_load_n(&attach_cancel_, __ATOMIC_ACQUIRE)) {
        nmx_marker_write(false);
        attach_ = -1;
        return;
    }
    printf("NullMoth GPU: stage entering PCI driver attachment\n");
    setProperty("nullmoth-gpu-state", "attaching: PCI driver");
    dev_ = nmx_port_attach(pci_);
    printf("NullMoth GPU: stage PCI driver attachment returned %s\n",
          dev_ ? "device" : "null");
    if (dev_ == nullptr) {
        nmx_marker_write(false);
        printf("NullMoth GPU: no driver took %04x:%04x\n", pci_->configRead16(kIOPCIConfigVendorID),
              pci_->configRead16(kIOPCIConfigDeviceID));
        attach_ = -1;
        return;
    }

    static IOPMPowerState states[2] = {
        { kIOPMPowerStateVersion1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 },
        { kIOPMPowerStateVersion1, kIOPMPowerOn, kIOPMPowerOn, kIOPMPowerOn, 0, 0, 0, 0, 0, 0, 0, 0 },
    };
    PMinit();
    pci_->joinPMtree(this);
    registerPowerDriver(this, states, 2);
    pm_ = true;
    registerService();
    fb_ = nmx_fb_publish(this, dev_);
    if (fb_ == nullptr) {
        setProperty("nullmoth-gpu-state", "attached: framebuffer unavailable");
        nmx_marker_write(false);
        printf("NullMoth GPU: no framebuffer; withholding the accelerator claim\n");
        attach_ = -1;
        return;
    }
    /* Start accelerator matching only after the framebuffer exists. */
    pci_->setProperty("nmxgpu-claimed", kOSBooleanTrue);
    pci_->registerService();
    nmx_marker_write(false);
    printf("NullMoth GPU: driving %04x:%04x\n", pci_->configRead16(kIOPCIConfigVendorID),
          pci_->configRead16(kIOPCIConfigDeviceID));
    OSSynchronizeIO();
    attach_ = 1;
}

void NMXGPU::stop(IOService *provider)
{
    /* A timeout cannot grant ownership of resources still used by a worker.
       Cancellation prevents a queued worker from attaching; an in-flight driver
       call must finish before any framebuffer, PM or PCI resource is detached. */
    __atomic_store_n(&attach_cancel_, 1u, __ATOMIC_RELEASE);
    while (!__atomic_load_n(&attach_thread_done_, __ATOMIC_ACQUIRE))
        IOSleep(100);
    provider->removeProperty("nmxgpu-claimed");
    if (fb_ != nullptr)
        nmx_fb_unpublish(fb_, this, dev_);
    fb_ = nullptr;
    if (pm_)
        PMstop();
    pm_ = false;
    nmx_port_detach(dev_);
    dev_ = nullptr;
    IOLockLock(g_lock);
    g_devices--;
    IOLockUnlock(g_lock);
    IOService::stop(provider);
}

/* state 0 = sleep, 1 = on */
IOReturn NMXGPU::setPowerState(unsigned long state, IOService *device)
{
    if (dev_ != nullptr) {
        int err = nmx_port_power(dev_, state != 0);
        if (err)
            printf("NullMoth GPU: %s returned %d\n", state ? "resume" : "suspend", err);
    }
    return kIOPMAckImplied;
}

void NMXGPU::systemWillShutdown(IOOptionBits spec)
{
    if (dev_ != nullptr)
        nmx_port_shutdown(dev_);
    IOService::systemWillShutdown(spec);
}

/* ---- module start/stop: the stop refuses while device nodes are open ------------------------------------------------- */

extern "C" {
kern_return_t nmx_kmod_start(kmod_info_t *ki, void *data);
kern_return_t nmx_kmod_stop(kmod_info_t *ki, void *data);
}

kern_return_t nmx_kmod_start(kmod_info_t *ki, void *data)
{
    g_lock = IOLockAlloc();
    return g_lock ? KERN_SUCCESS : KERN_FAILURE;
}

kern_return_t nmx_kmod_stop(kmod_info_t *ki, void *data)
{
    IOLockLock(g_lock);
    if (g_devices > 0) {
        IOLockUnlock(g_lock);
        return KERN_FAILURE;
    }
    if (g_started) {
        if (nmx_port_busy() > 0) {
            IOLockUnlock(g_lock);
            printf("NullMoth GPU: still in use; not unloading\n");
            return KERN_FAILURE;
        }
        nmx_port_stop();
        g_started = false;
    }
    IOLockUnlock(g_lock);
    IOLockFree(g_lock);
    g_lock = nullptr;
    return KERN_SUCCESS;
}

/* libkmod's entry points; they call _realmain/_antimain below */
extern "C" {
kern_return_t _start(kmod_info_t *ki, void *data);
kern_return_t _stop(kmod_info_t *ki, void *data);
KMOD_EXPLICIT_DECL(com.nullmoth.NMXGPU, "1.0.0", _start, _stop)
__private_extern__ kmod_start_func_t *_realmain = nmx_kmod_start;
__private_extern__ kmod_stop_func_t *_antimain = nmx_kmod_stop;
}

int NMXGPU::startRuntime()
{
    IOLockLock(g_lock);
    if (!g_started) {
        int guc = 0;
        if (PE_parse_boot_argn("nmxguc", &guc, sizeof(guc))) {
            int policy_error = nmx_i915_set_guc_mode(guc);
            if (policy_error) {
                IOLockUnlock(g_lock);
                printf("NullMoth GPU: invalid nmxguc=%d (expected 0..3)\n", guc);
                return policy_error;
            }
            printf("NullMoth GPU: explicit i915 enable_guc=%d before port initialization\n", guc);
        }
        printf("CUG-B4: before port-start IF=%d\n", ml_get_interrupts_enabled());
        int err = nmx_port_start();
        printf("CUG-B4: after port-start error=%d IF=%d\n", err, ml_get_interrupts_enabled());
        if (err) {
            IOLockUnlock(g_lock);
            printf("NullMoth GPU: the driver layer did not start (%d)\n", err);
            return err;
        }
        printf("NullMoth GPU: stage port-start returned successfully\n");
        g_started = true;
    }
    IOLockUnlock(g_lock);
    return 0;
}
