"""Execute the real GPIO configuration method against mock MMIO registers."""
from pathlib import Path
import re, shutil, subprocess, tempfile

source = (Path(__file__).resolve().parents[1]/'VoodooGPIOIntel.cpp').read_text()
begin = source.index('bool VoodooGPIOIntel::intel_gpio_irq_set_type(')
end = source.index('\nbool VoodooGPIOIntel::intel_pinctrl_add_padgroups', begin)
method = source[begin:end]
defines = '\n'.join(line for line in source.splitlines() if line.startswith('#define PADCFG0'))
program = r'''
#include <cassert>
#include <cstdint>
#include <cstring>
#include <map>
#include <string>
#define BIT(n) (uint32_t(1) << (n))
#define GENMASK(h,l) ((~uint32_t(0) >> (31-(h))) & (~uint32_t(0) << (l)))
#define IRQ_TYPE_EDGE_RISING 1
#define IRQ_TYPE_EDGE_FALLING 2
#define IRQ_TYPE_EDGE_BOTH 3
#define IRQ_TYPE_LEVEL_HIGH 4
#define IRQ_TYPE_LEVEL_LOW 8
#define IRQ_TYPE_LEVEL_MASK 12
#define TryLog(...) ((void)0)
DEFINES
using UInt32 = uint32_t;
using IOVirtualAddress = uintptr_t;
static UInt32 mmio;
static bool locked = false;
static UInt32 readl(IOVirtualAddress) { return mmio; }
static void writel(UInt32 value, IOVirtualAddress) { if (!locked) mmio = value; }
struct Meta { const char *name = "VoodooGPIOMeteorLakeP"; const char *getClassName() { return name; } };
struct VoodooGPIOIntel {
    Meta meta;
    bool acpi = false, missing = false;
    std::map<std::string, UInt32> properties;
    IOVirtualAddress intel_get_padcfg(unsigned, unsigned) { return missing ? 0 : 1; }
    bool intel_pad_acpi_mode(unsigned) { return acpi; }
    const char *getName() { return meta.name; }
    Meta *getMetaClass() { return &meta; }
    void setProperty(const char *name, UInt32 v, unsigned) { properties[name] = v; }
    void setProperty(const char *name, bool v) { properties[name] = v; }
    bool intel_gpio_irq_set_type(unsigned pin, unsigned type);
};
METHOD
int main() {
    VoodooGPIOIntel p;
    constexpr UInt32 routes = BIT(20)|BIT(19)|BIT(18)|BIT(17);
    constexpr UInt32 preserve = BIT(30)|BIT(28)|BIT(24)|BIT(7)|BIT(1)|BIT(0);
    constexpr UInt32 bad = routes|PADCFG0_PMODE_MASK|PADCFG0_GPIORXDIS|PADCFG0_RXEVCFG_MASK;
    // Low-level ELAN IRQ: restore receiver, disable output, remove all direct routes.
    mmio = bad|preserve;
    assert(p.intel_gpio_irq_set_type(232, IRQ_TYPE_LEVEL_LOW));
    assert((mmio & (routes|PADCFG0_PMODE_MASK|PADCFG0_GPIORXDIS|PADCFG0_RXEVCFG_MASK)) == 0);
    assert((mmio & (PADCFG0_GPIOTXDIS|PADCFG0_RXINV)) == (PADCFG0_GPIOTXDIS|PADCFG0_RXINV));
    assert((mmio & preserve) == preserve);
    assert(p.properties["LatitudeELANPadConfigVerified"] == 1);
    // High-level and falling-edge polarity/event configuration still work.
    mmio = bad|preserve;
    assert(p.intel_gpio_irq_set_type(232, IRQ_TYPE_LEVEL_HIGH));
    assert(!(mmio & PADCFG0_RXINV));
    assert(p.intel_gpio_irq_set_type(232, IRQ_TYPE_EDGE_FALLING));
    assert((mmio & PADCFG0_RXEVCFG_MASK) == BIT(25));
    assert(mmio & PADCFG0_RXINV);
    // Read-only pad: reject the configuration instead of claiming an IRQ works.
    mmio = bad|preserve; locked = true;
    assert(!p.intel_gpio_irq_set_type(232, IRQ_TYPE_LEVEL_LOW));
    assert(p.properties["LatitudeELANPadConfigVerified"] == 0);
    locked = false;
    // Firmware ownership failure and missing mapping must not write a register.
    p.acpi = true; mmio = bad;
    assert(!p.intel_gpio_irq_set_type(232, IRQ_TYPE_LEVEL_LOW) && mmio == bad);
    p.acpi = false; p.missing = true;
    assert(!p.intel_gpio_irq_set_type(232, IRQ_TYPE_LEVEL_LOW) && mmio == bad);
    p.missing = false;
    // Wacom's hardware pad and older platforms retain the old routing behavior.
    mmio = bad;
    assert(p.intel_gpio_irq_set_type(225, IRQ_TYPE_LEVEL_LOW));
    assert((mmio & (routes|PADCFG0_GPIORXDIS)) == (routes|PADCFG0_GPIORXDIS));
    p.meta.name = "VoodooGPIOIceLakeLP"; mmio = bad;
    assert(p.intel_gpio_irq_set_type(232, IRQ_TYPE_LEVEL_LOW));
    assert((mmio & (routes|PADCFG0_GPIORXDIS)) == (routes|PADCFG0_GPIORXDIS));
}
'''.replace('DEFINES', defines).replace('METHOD', method)
compiler = shutil.which('clang++') or shutil.which('g++')
assert compiler, 'C++ compiler required for GPIO MMIO regression cases'
with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    (tmp/'gpio.cpp').write_text(program)
    exe = tmp/'gpio-test'
    subprocess.run([compiler, '-std=c++17', str(tmp/'gpio.cpp'), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True)
print('Real GPIO method: low/high/edge, preserved bits, locked pad, ownership, absent mapping and device scope passed.')
