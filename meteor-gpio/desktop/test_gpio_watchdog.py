"""Exercise the actual level watchdog with simulated GPIO and a HID callback."""
from pathlib import Path
import shutil, subprocess, tempfile
root = Path(__file__).resolve().parents[1]
s = (root/'VoodooGPIOIntel.cpp').read_text()
method = s[s.index('void VoodooGPIOIntel::latitudeELANWatchdog('):]
defines = '\n'.join(line for line in s.splitlines() if line.startswith('#define PADCFG0'))
program = r'''
#include <cassert>
#include <cstdint>
#include <map>
#include <string>
#define BIT(n) (uint32_t(1) << (n))
#define GENMASK(h,l) ((~uint32_t(0) >> (31-(h))) & (~uint32_t(0) << (l)))
#define GPI_IS 0x100
DEFINES
using UInt32 = uint32_t; using UInt64 = uint64_t; using SInt32 = int32_t;
using IOVirtualAddress = uintptr_t;
struct OSObject {};
struct IOService : OSObject {};
struct IOTimerEventSource { unsigned next = 0; void setTimeoutMS(unsigned n) { next = n; } };
using IOInterruptAction = void (*)(OSObject *, void *, IOService *, int);
struct intel_padgroup { unsigned base = 229, reg_num = 1; };
struct intel_community {
    unsigned pin_base = 204, ie_offset = 0x210, is_offset = 0x200;
    IOVirtualAddress regs = 0x2000;
    OSObject *pinInterruptActionOwners[85] = {};
    IOInterruptAction pinInterruptAction[85] = {};
    void *pinInterruptRefcons[85] = {};
};
static std::map<IOVirtualAddress, UInt32> mmio;
static unsigned reads = 0, callbacks = 0;
static UInt32 readl(IOVirtualAddress addr) { ++reads; return mmio[addr]; }
static void input(OSObject *, void *, IOService *, int pin) {
    assert(pin == 387); ++callbacks;
    // Apple's level-triggered event source masks the pin while the HID work is queued.
    mmio[0x2214] = 0;
}
struct VoodooGPIOIntel : IOService {
    bool controllerIsAwake = true, missingPad = false;
    SInt32 mapping = 232;
    intel_community community;
    intel_padgroup group;
    UInt64 latitude_elan_ticks = 0, latitude_elan_low_samples = 0, latitude_elan_dispatches = 0;
    UInt32 latitude_parent_irqs = 0;
    std::map<std::string, UInt64> properties;
    SInt32 intel_gpio_to_pin(unsigned pin, intel_community **c, intel_padgroup **g) {
        assert(pin == 387); *c = &community; *g = &group; return mapping;
    }
    IOVirtualAddress intel_get_padcfg(unsigned pin, unsigned reg) {
        assert(pin == 232 && reg == PADCFG0); return missingPad ? 0 : 0x1000;
    }
    void setProperty(const char *name, UInt64 value, unsigned) { properties[name] = value; }
    void latitudeELANWatchdog(OSObject *, IOTimerEventSource *);
};
METHOD
int main() {
    VoodooGPIOIntel p; IOTimerEventSource timer; OSObject target;
    p.community.pinInterruptActionOwners[28] = &target;
    p.community.pinInterruptAction[28] = input;
    // Idle high: no HID callback or bus request, normal two-ms rearm.
    mmio[0x1000] = 0x90800102; mmio[0x2214] = BIT(3); mmio[0x2204] = 0;
    p.latitudeELANWatchdog(nullptr, &timer);
    assert(callbacks == 0 && timer.next == 2 && p.latitude_elan_ticks == 1);
    // Physical line low, even with no GPI_IS/CPU IRQ: queue the HID read.
    mmio[0x1000] &= ~PADCFG0_GPIORXSTATE;
    p.latitudeELANWatchdog(nullptr, &timer);
    assert(callbacks == 1 && p.latitude_elan_dispatches == 1);
    assert(p.properties["LatitudeELANParentIRQs"] == 0);
    // Respect the mask: no duplicate read while the workloop services input.
    p.latitudeELANWatchdog(nullptr, &timer); assert(callbacks == 1);
    // Re-enable with line still low: more queued input must be drained.
    mmio[0x2214] = BIT(3);
    p.latitudeELANWatchdog(nullptr, &timer); assert(callbacks == 2);
    // RX disabled, output direction and alternate mux cannot trigger a read.
    mmio[0x2214] = BIT(3); mmio[0x1000] |= PADCFG0_GPIORXDIS;
    p.latitudeELANWatchdog(nullptr, &timer); assert(callbacks == 2);
    mmio[0x1000] = 0;
    p.latitudeELANWatchdog(nullptr, &timer); assert(callbacks == 2);
    mmio[0x1000] = PADCFG0_GPIOTXDIS | BIT(10);
    p.latitudeELANWatchdog(nullptr, &timer); assert(callbacks == 2);
    // Never access MMIO while asleep.
    p.controllerIsAwake = false; unsigned before = reads;
    p.latitudeELANWatchdog(nullptr, &timer);
    assert(reads == before && timer.next == 20 && callbacks == 2);
    p.controllerIsAwake = true;
    // An unregistered subscriber, wrong mapping or absent pad must not be called/rearmed.
    p.community.pinInterruptActionOwners[28] = nullptr; timer.next = 0;
    p.latitudeELANWatchdog(nullptr, &timer); assert(callbacks == 2 && timer.next == 0);
    p.community.pinInterruptActionOwners[28] = &target;
    p.mapping = -1;
    p.latitudeELANWatchdog(nullptr, &timer); assert(callbacks == 2 && timer.next == 0);
    p.mapping = 232; p.missingPad = true;
    p.latitudeELANWatchdog(nullptr, &timer); assert(callbacks == 2 && timer.next == 0);
}
'''.replace('DEFINES', defines).replace('METHOD', method)
with tempfile.TemporaryDirectory() as folder:
    folder = Path(folder)
    (folder/'test.cpp').write_text(program)
    exe = folder/'test'
    compiler = shutil.which('clang++') or shutil.which('g++')
    assert compiler
    subprocess.run([compiler, '-std=c++17', str(folder/'test.cpp'), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True)
stop = s[s.index('void VoodooGPIOIntel::stop('):s.index('IOReturn VoodooGPIOIntel::setPowerState(')]
assert stop.index('latitude_elan_timer->cancelTimeout()') < stop.index('OSSafeReleaseNULL(communities[i].mmap)')
assert 'pin == 387 && latitude_elan_timer' in s
print('Actual GPIO watchdog: idle-high, low without CPU IRQ, mask/drain, invalid pin state, sleep, unregister and teardown cases passed.')
