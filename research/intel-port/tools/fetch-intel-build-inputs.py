"""Fetch pinned source/header inputs only. Does not install firmware or kexts."""
from pathlib import Path, PurePosixPath
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import tarfile
import urllib.request

root=Path(__file__).resolve().parents[1]
inputs=root/'tooling/build-inputs'
inputs.mkdir(parents=True,exist_ok=True)
archives=[
 ('https://codeload.github.com/freebsd/drm-kmod/tar.gz/c16de0f9fa84f70b9551f69fde837a7f3a73c0e9',
  'drm-kmod-c16de0f9.tar.gz','4515282c690c0f88d936fd4919e691f1125e8f14b5fc124160d799f098bf61e7',inputs),
 ('https://codeload.github.com/acidanthera/MacKernelSDK/tar.gz/3f750085caa17ec3a7880f11c11bf4f48cd6a164',
  'MacKernelSDK-3f750085.tar.gz','8931e622b6d16a7052cb2c2dabe16be06963a34b747f19e6cda2bbe8bc7e2557',inputs),
 ('https://codeload.github.com/nullmoth/nvidia-macos-driver/tar.gz/277a29bea10371a88c4c1fb104409060d31962e8',
  'nullmoth-277a29be.tar.gz','de441608eb81a863c82dce29015950e97a39e2cacade186efb38b24b7f9a10a5',inputs),
 ('https://github.com/nullmoth/nvidia-macos-driver/releases/download/v2.1.0/nmxnpu-source-2.1.0.tar.gz',
  'nmxnpu-source-2.1.0.tar.gz','9dd7c229e1e05cb6c574dfc7623cc3d467f84eb9f39ab4913203a36aaf1d4747',
  root/'upstream/nmxnpu-source-2.1.0'),
]

def download(url,path,expected):
    if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest()==expected:
        return
    request=urllib.request.Request(url,headers={'User-Agent':'CoreUltraGraphics-source-build'})
    with urllib.request.urlopen(request,timeout=90) as response:
        data=response.read()
    if hashlib.sha256(data).hexdigest()!=expected:
        raise RuntimeError('SHA256 mismatch: '+url)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(data)

for url,name,digest,dest in archives:
    archive=inputs/name
    download(url,archive,digest)
    dest.mkdir(parents=True,exist_ok=True)
    with tarfile.open(archive) as tar:
        files=[]
        for entry in tar:
            relative=PurePosixPath(entry.name)
            if not entry.isfile():
                continue
            if relative.is_absolute() or '..' in relative.parts:
                raise RuntimeError('Unsafe source archive member')
            files.append(entry)
        tar.extractall(dest,members=files,filter='data')
    print('Verified and extracted',name,flush=True)

manifest=json.loads((root/'pins/linuxkpi-headers.json').read_text())
target=inputs/'freebsd-linuxkpi-full'
def header(record):
    path=record['path']
    if '..' in PurePosixPath(path).parts or PurePosixPath(path).is_absolute():
        raise RuntimeError('Unsafe header path')
    url='https://raw.githubusercontent.com/freebsd/freebsd-src/'+manifest['commit']+'/sys/compat/linuxkpi/'+path
    download(url,target/path,record['sha256'])
with ThreadPoolExecutor(max_workers=10) as pool:
    list(pool.map(header,manifest['files']))
print('Verified',len(manifest['files']),'LinuxKPI headers at',manifest['commit'])
