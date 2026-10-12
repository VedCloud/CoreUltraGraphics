"""Prepare a NEW config candidate with the experimental kext disabled."""
import argparse
import copy
import plistlib
from pathlib import Path

ENTRY = dict(Arch='x86_64', BundlePath='CoreUltraGraphics.kext', Enabled=False,
             Comment='Experimental PCI probe; no acceleration',
             ExecutablePath='Contents/MacOS/CoreUltraGraphics', MaxKernel='',
             MinKernel='20.0.0', PlistPath='Contents/Info.plist')

def prepare(data):
    result = copy.deepcopy(data)
    if not isinstance(result, dict):
        raise ValueError('Invalid configuration root')
    kernel = result.setdefault('Kernel', {})
    if not isinstance(kernel, dict):
        raise ValueError('Invalid Kernel section')
    entries = kernel.setdefault('Add', [])
    if not isinstance(entries, list) or any(not isinstance(e, dict) for e in entries):
        raise ValueError('Invalid Kernel/Add')
    matches = [e for e in entries if e.get('BundlePath') == ENTRY['BundlePath']]
    if len(matches) > 1:
        raise ValueError('Duplicate probe entries require review')
    if matches:
        matches[0]['Enabled'] = False
    else:
        entries.append(dict(ENTRY))
    return result

def write_candidate(source, output):
    source, output = Path(source), Path(output)
    if source.resolve() == output.resolve():
        raise ValueError('Input and output must differ')
    candidate = prepare(plistlib.loads(source.read_bytes()))
    with output.open('xb') as stream:
        stream.write(plistlib.dumps(candidate, sort_keys=False))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('config')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    try:
        write_candidate(args.config, args.output)
    except (OSError, ValueError, plistlib.InvalidFileException):
        parser.exit(2, 'Cannot prepare candidate; use valid input and a new output path.\n')
    print('Candidate created with probe disabled; input unchanged. No installation performed.')
