"""Offline bundle/header validation; not a loadability or hardware test."""
import argparse
import plistlib
import struct
from pathlib import Path


def check_macho(raw):
    if len(raw) < 32:
        raise ValueError('truncated Mach-O header')
    magic, cpu, subtype, filetype, commands, command_bytes, flags, reserved = struct.unpack_from('<8I', raw)
    if magic != 0xfeedfacf or cpu != 0x01000007 or filetype != 11:
        raise ValueError('expected thin x86_64 MH_KEXT_BUNDLE')
    if command_bytes > len(raw) - 32 or commands > command_bytes // 8:
        raise ValueError('invalid load-command bounds')
    cursor = 32
    for _ in range(commands):
        if cursor + 8 > 32 + command_bytes:
            raise ValueError('truncated load command')
        _, length = struct.unpack_from('<2I', raw, cursor)
        if length < 8 or length % 8 or length > 32 + command_bytes - cursor:
            raise ValueError('invalid load-command size')
        cursor += length
    if cursor != 32 + command_bytes:
        raise ValueError('inconsistent load-command count')


def verify_bundle(bundle):
    info = plistlib.loads((bundle / 'Contents/Info.plist').read_bytes())
    if info.get('CFBundleIdentifier') != 'com.custom.CoreUltraGraphics':
        raise ValueError('unexpected bundle identifier')
    if info.get('CFBundleExecutable') != 'CoreUltraGraphics':
        raise ValueError('unexpected executable')
    if info.get('CFBundlePackageType') != 'KEXT':
        raise ValueError('unexpected package type')
    check_macho((bundle / 'Contents/MacOS/CoreUltraGraphics').read_bytes())


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bundle', type=Path)
    args = parser.parse_args()
    try:
        verify_bundle(args.bundle)
    except (OSError, ValueError, plistlib.InvalidFileException):
        parser.exit(2, 'Bundle/header validation failed.\n')
    print('Thin x86_64 kext bundle/header valid; runtime compatibility NOT established.')
