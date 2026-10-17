"""Rebuild the DRM core, LinuxKPI, XNU adapter and IOKit glue for an Intel-only port."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter
import hashlib
import json
import subprocess
import sys

root=Path(__file__).resolve().parents[1]
inputs=root/'tooling/build-inputs'
port=inputs/'nvidia-macos-driver-277a29bea10371a88c4c1fb104409060d31962e8/gpu-port/xkpi'
archive=root/'upstream/nmxnpu-source-2.1.0/nmxnpu-source'
d=inputs/'drm-kmod-c16de0f9fa84f70b9551f69fde837a7f3a73c0e9'
out=root/'evidence/intel-runtime-build'
out.mkdir(parents=True,exist_ok=True)
template=json.loads((root/'evidence/intel-bridge-build/nmx_i915_bridge.c.compile-command.json').read_text())
base=template[:template.index('-c')]+['-DNMX_INTEL_ONLY=1']
cpp=json.loads((root/'evidence/intel-bridge-build/nmx_kext.cpp.compile-command.json').read_text())
cppbase=cpp[:cpp.index('-c')]
flags=root/'evidence/intel-driver-build/build.flags'
listed=subprocess.run([sys.executable,str(port/'srclist.py'),str(d),str(flags),'drm','ttm','dmabuf'],
                       capture_output=True,text=True,check=True)
assert not listed.stderr,listed.stderr
excluded=set('drm_gem_ttm_helper.c drm_writeback.c drm_hdcp_helper.c sync_file.c dma-fence-unwrap.c dma-buf.c dma-buf-kmod.c linux_fb.c vt_drmfb.c drm_os_freebsd.c'.split())
sources=[Path(p) for p in listed.stdout.splitlines() if Path(p).name not in excluded]
sources += [d/'drivers/gpu/drm'/f for f in ('drm_client.c','drm_client_modeset.c','drm_panel_orientation_quirks.c','drm_mipi_dsi.c')]
skip=set('linux_80211 linux_80211_macops linuxkpi_80211_pm linux_netdev linux_usb linux_i2c linux_i2cbb linux_cmdline linux_eventfd'.split())
overrides={p.name:p for p in (port/'override/src').glob('*.c')}
for p in (archive/'upstream/kpi/freebsd-src/sys/compat/linuxkpi/common/src').glob('*.c'):
    if p.stem not in skip and p.name not in overrides:
        sources.append(p)
sources += [p for p in overrides.values() if p.stem not in skip and p.name!='nmx_fb_bridge.c']
sources += list((port/'bsdcompat/src').glob('*.c'))
sources += [archive/'upstream/kpi/freebsd-src/sys/contrib/ck/src/ck_epoch.c']
sources += [p for p in (port/'xnu').glob('*.cpp') if p.name not in ('nmx_npu_kext.cpp','nmx_kext.cpp')]
sources += [root/'port/nullmoth-candidate'/f for f in ('nmx_kext.cpp','nmx_fb_bridge.c','nmx_i915_bridge.c')]
sources = [root/'port/nullmoth-candidate'/p.name if p.name in ('nmx_misc.c','nmx_platform.cpp') else p for p in sources]
sources=list(dict.fromkeys(sources))

def build(path):
    key=path.stem+'-'+hashlib.sha256(str(path).encode()).hexdigest()[:8]
    command=(cppbase if path.suffix=='.cpp' else base)+['-c',str(path),'-o',str(out/(key+'.o'))]
    run=subprocess.run(command,capture_output=True,text=True)
    (out/(key+'.log')).write_text(run.stdout+run.stderr,encoding='utf-8')
    return dict(source=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),exit_code=run.returncode,
                object=key+'.o',errors=[s for s in run.stderr.splitlines() if 'error:' in s])

results=[]
sources_to_build=sources
if '--retry-failed' in sys.argv and (out/'results.json').exists():
    previous=json.loads((out/'results.json').read_text())
    passed={r['source']:r for r in previous['results'] if r['exit_code']==0}
    results=[passed[str(p)] for p in sources if str(p) in passed]
    sources_to_build=[p for p in sources if str(p) not in passed]
with ThreadPoolExecutor(max_workers=4) as pool:
    for future in as_completed([pool.submit(build,p) for p in sources_to_build]):
        results.append(future.result())
        if len(results)%40==0:print('Compiled',len(results),'of',len(sources),flush=True)
report=dict(source_count=len(sources),passed=sum(r['exit_code']==0 for r in results),results=results,linked=False,installed=False)
(out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
errors=Counter(s.split('error:',1)[-1].strip() for r in results for s in r['errors'])
print(json.dumps(dict(source_count=len(sources),passed=report['passed'],errors=errors),indent=2))
