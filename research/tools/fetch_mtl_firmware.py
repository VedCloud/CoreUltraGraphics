"""Acquire pinned upstream MTL firmware; verify Git blob identities; never load it."""
import base64
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
COMMIT = '38c1a7096dfb2188f55f342b835f14c362c59409'
BASE = 'https://kernel.googlesource.com/pub/scm/linux/kernel/git/firmware/linux-firmware'
NAMES = ['i915/mtl_guc_70.bin', 'i915/mtl_huc_gsc.bin', 'i915/mtl_gsc_1.bin',
         'i915/mtl_dmc.bin', 'WHENCE', 'LICENSES/LICENSE.i915']


def get(url):
    with urllib.request.urlopen(url, timeout=60) as response:
        return response.read()


def main():
    folder = ROOT / 'firmware' / COMMIT[:12]
    folder.mkdir(parents=True, exist_ok=True)
    trees = {}
    records = []
    for name in NAMES:
        parent, _, leaf = name.rpartition('/')
        if parent not in trees:
            url = f'{BASE}/+/{COMMIT}/{parent}/?format=JSON'
            trees[parent] = {e['name']: e for e in json.loads(get(url)[4:])['entries']}
        expected = trees[parent][leaf]
        if expected['mode'] != 0o100644 or expected['type'] != 'blob':
            raise RuntimeError(f'Unexpected non-regular upstream entry: {name}')
        url = f'{BASE}/+/{COMMIT}/{name}?format=TEXT'
        data = base64.b64decode(get(url), validate=True)
        blob = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
        if blob != expected['id']:
            raise RuntimeError(f'Git blob mismatch: {name}')
        target = folder / leaf
        if target.exists() and target.read_bytes() != data:
            raise RuntimeError(f'Refusing to overwrite different bytes: {target}')
        target.write_bytes(data)
        records.append({'upstream_path': name, 'local_path': target.relative_to(ROOT).as_posix(),
                        'url': url, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(),
                        'git_blob_sha1': blob})
    manifest = {'repository': BASE, 'commit': COMMIT,
                'verification': 'downloaded bytes match pinned upstream Git blob IDs; '
                                'no Intel RSA signature verification performed',
                'files': records}
    (folder / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print(f'Acquired and verified {len(records)} files in {folder}')


if __name__ == '__main__':
    main()
