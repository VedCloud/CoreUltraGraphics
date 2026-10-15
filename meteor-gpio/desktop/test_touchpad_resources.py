"""Exercise the upstream resource parser against captured firmware descriptors."""
from pathlib import Path
import subprocess
import tempfile


def run():
    root = Path.cwd()
    deps = root/'.deps/VoodooI2C/Dependencies/VoodooI2CACPIResourcesParser'
    serial = bytes.fromhex('8e1e00010001020000010600801a06002c005c5f53422e504330302e49324333007900')
    gpio = bytes.fromhex('8c2000010001001200000000000017000019002300000083015c5f53422e47504930007900')
    table = (root/'meteor-gpio/VoodooGPIOMeteorLakeP.hpp').read_text()
    assert 'MTL_GPP(1, 229, 253, 384)' in table
    assert 229 + int.from_bytes(gpio[23:25], 'little') - 384 == 232
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        (tmp/'IOKit').mkdir()
        (tmp/'IOKit/IOLib.h').write_text('#pragma once\n')
        array = lambda b: ','.join(str(n) for n in b)
        source = '''#include <cassert>
#include "VoodooI2CACPIResourcesParser.hpp"
int main() {
    const uint8_t serial[] = {SERIAL};
    const uint8_t gpio[] = {GPIO};
    VoodooI2CACPIResourcesParser p;
    p.parseACPIResources(serial, 0, sizeof(serial));
    assert(p.found_i2c && !p.found_gpio_interrupts);
    assert(p.i2c_info.address == 0x2c && p.i2c_info.bus_speed == 400000);
    p.parseACPIResources(gpio, 0, sizeof(gpio));
    assert(p.found_i2c && p.found_gpio_interrupts);
    assert(p.gpio_interrupts.pin_number == 0x183);
    assert(p.gpio_interrupts.level_interrupt);
    assert(p.gpio_interrupts.interrupt_polarity == 1);
    assert(p.gpio_interrupts.irq_type == 8);
    // A Wacom descriptor must not be mistaken for the physical touchpad.
    uint8_t other[sizeof(gpio)];
    for (unsigned i = 0; i < sizeof(gpio); ++i) other[i] = gpio[i];
    other[23] = 0x75;
    VoodooI2CACPIResourcesParser w;
    w.parseACPIResources(other, 0, sizeof(other));
    assert(w.gpio_interrupts.pin_number == 0x175);
    assert(w.gpio_interrupts.pin_number != p.gpio_interrupts.pin_number);
}
'''.replace('SERIAL', array(serial)).replace('GPIO', array(gpio))
        (tmp/'test.cpp').write_text(source)
        exe = tmp/'test'
        subprocess.run(['clang++', '-std=c++17', '-I'+str(tmp), '-I'+str(deps),
                        str(deps/'VoodooI2CACPIResourcesParser.cpp'), str(tmp/'test.cpp'),
                        '-o', str(exe)], check=True)
        subprocess.run([str(exe)], check=True)
    print('Captured ELAN I2C/GPIO parser and separate Wacom pin checks passed.')


if __name__ == '__main__':
    run()
