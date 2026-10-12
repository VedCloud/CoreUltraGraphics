"""Read Linux PCI sysfs metadata only; never opens config, resource or ROM files."""
import argparse
import json
from pathlib import Path


def hex_field(folder, name, bits):
    text = (folder / name).read_text(encoding='ascii').strip()
    value = int(text, 16)
    if not 0 <= value < (1 << bits):
        raise ValueError('out-of-range PCI field')
    return value


def collect(root):
    root = Path(root)
    if not root.is_dir():
        raise ValueError('PCI sysfs directory unavailable')
    devices, errors = [], []
    for folder in sorted(root.iterdir()):
        if not folder.is_dir():
            continue
        try:
            pci_class = hex_field(folder, 'class', 24)
            if pci_class >> 16 != 3:
                continue
            vendor = hex_field(folder, 'vendor', 16)
            device = hex_field(folder, 'device', 16)
            revision = hex_field(folder, 'revision', 8)
            driver = folder / 'driver'
            devices.append({'vendor': f'{vendor:04x}', 'device': f'{device:04x}',
                            'revision': f'{revision:02x}', 'class': f'{pci_class:06x}',
                            'driver': driver.resolve().name if driver.is_symlink() else None,
                            'configured_probe_match': vendor == 0x8086 and device == 0x7d45})
        except (OSError, ValueError):
            # No paths or raw values emitted. Partial data is explicitly identified.
            errors.append({'entry_index': len(devices) + len(errors),
                           'error': 'PCI metadata unreadable or invalid'})
    return {'display_devices': devices, 'errors': errors,
            'scope': 'PCI metadata only; no acceleration, firmware or GPU execution test'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sysfs', type=Path, default=Path('/sys/bus/pci/devices'))
    args = parser.parse_args()
    try:
        result = collect(args.sysfs)
    except ValueError:
        parser.exit(2, 'PCI sysfs directory unavailable; run on Linux or use fixture input.\n')
    print(json.dumps(result, indent=2))
    raise SystemExit(1 if result['errors'] else 0)
