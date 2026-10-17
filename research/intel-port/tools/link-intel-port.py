"""Link an Intel-only experimental NMXGPU on macOS. Never installs the result."""
from pathlib import Path
import hashlib
import json
import plistlib
import re
import subprocess
import sys
import os

root=Path(__file__).resolve().parents[1]
if sys.platform!='darwin':
    raise SystemExit('The final kext link requires macOS/Xcode (local Windows Zig does not support -kext).')
objects=[]
for folder in ('intel-driver-build','intel-runtime-build'):
    directory=root/'evidence'/folder
    report=json.loads((directory/'results.json').read_text())
    if report['passed']!=report['source_count']:
        raise SystemExit('Incomplete source compilation: '+folder)
    for row in report['results']:
        source=Path(row['source'])
        if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest()!=row['sha256']:
            raise SystemExit('Compiled source differs from this checkout: '+str(source))
        objects.append(directory/row['object'])
out=root/'evidence/intel-linked-build'
binary=out/'NMXGPU.kext/Contents/MacOS/NMXGPU'
binary.parent.mkdir(parents=True,exist_ok=True)
compiler=subprocess.check_output(['xcrun','--find','clang++'],text=True).strip()
sdk=subprocess.check_output(['xcrun','--sdk','macosx','--show-sdk-path'],text=True).strip()
kernel_sdk=root/'tooling/build-inputs/MacKernelSDK-3f750085caa17ec3a7880f11c11bf4f48cd6a164'
command=[compiler,'-arch','x86_64','-mmacosx-version-min=15.0','-mkernel','-fapple-kext',
         '-static','-nostdlib','-isysroot',sdk,
         '-L'+str(kernel_sdk/'Library/x86_64'),'-L'+str(kernel_sdk/'Library/universal'),
         '-Xlinker','-kext','-Xlinker','-no_deduplicate',
         *map(str,objects),'-lkmodc++','-lkmod','-lcc_kext','-o',str(binary)]
run=subprocess.run(command,capture_output=True,text=True)
(out/'link.log').write_text(run.stdout+run.stderr)
if run.returncode:
    print(run.stdout+run.stderr)
    raise SystemExit(run.returncode)
public=root/'tooling/build-inputs/nvidia-macos-driver-277a29bea10371a88c4c1fb104409060d31962e8/gpu-port/xkpi'
info=plistlib.loads((public/'kext/Info.plist').read_bytes())
info['IOKitPersonalities'].pop('NMXGPUAMD',None)
info['IOKitPersonalities']['NMXGPUIntel']['IOPCIPrimaryMatch']='0x7d458086'
info['NMXExperimentalBuild']='CoreUltraGraphics: Intel-only GuC option and GGTT scanout candidate'
(binary.parent.parent/'Info.plist').write_bytes(plistlib.dumps(info))
imports=subprocess.check_output(['nm','-u',str(binary)],text=True)
exports=subprocess.check_output(['nm','-gU',str(binary)],text=True)
(out/'undefined-symbols.txt').write_text(imports)
(out/'defined-symbols.txt').write_text(exports)
bad=[line for line in imports.splitlines() if re.search(r'\b_(?:nmx_|lkpi_|i915_|intel_|drm_|linux_|ttm_|nmxkpi_)',line)]
if bad or not re.search(r'\b_kmod_info\b',exports):
    raise SystemExit('Kext symbol verification failed: '+str(bad))
subprocess.run(['plutil','-lint',str(binary.parent.parent/'Info.plist')],check=True)
subprocess.run(['otool','-hv',str(binary)],check=True)
result=dict(sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),objects=len(objects),
            source_build_run=os.environ.get('SOURCE_BUILD_RUN'),
            hardware_tested=False,metal_verified=False,installed=False)
(out/'LICENSE.NULLMOTH.txt').write_bytes((root/'LICENSE.NULLMOTH.txt').read_bytes())
(out/'build-result.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
