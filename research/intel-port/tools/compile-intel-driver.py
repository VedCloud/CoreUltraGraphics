"""Attempt a source rebuild of all selected i915 translation units; no installation."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import subprocess
import sys
from collections import Counter

root=Path(__file__).resolve().parents[1]
out=root/'evidence/intel-driver-build'
out.mkdir(parents=True,exist_ok=True)
inputs=root/'tooling/build-inputs'
port=inputs/'nvidia-macos-driver-277a29bea10371a88c4c1fb104409060d31962e8/gpu-port/xkpi'
d=inputs/'drm-kmod-c16de0f9fa84f70b9551f69fde837a7f3a73c0e9'
flags=out/'build.flags'
template=json.loads((root/'evidence/intel-bridge-build/nmx_i915_bridge.c.compile-command.json').read_text())
flags.write_text('\n'.join(s for s in template if s.startswith('-DCONFIG_'))+'\n')
generated=out/'forks'
generated.mkdir(exist_ok=True)
for name in ('i915_gem_mman','i915_module'):
    subprocess.run([sys.executable,str(port/('fork_'+name+'.py')),str(d),str(generated/(name+'.c'))],check=True,capture_output=True)
listed=subprocess.run([sys.executable,str(port/'srclist.py'),str(d),str(flags),'i915'],
                      capture_output=True,text=True,check=True)
assert not listed.stderr,listed.stderr
excluded={'intel_ggtt_gmch.c','i915_gem_mman.c','i915_module.c'}
sources=[Path(p) for p in listed.stdout.splitlines() if Path(p).name not in excluded]
sources+=list(generated.glob('*.c'))
sources+=list((port/'override/i915').glob('nmx_*.c'))
cut=template.index('-c')
base=template[:cut]

def build(path):
    key=path.stem+'-'+hashlib.sha256(str(path).encode()).hexdigest()[:8]
    command=base+['-c',str(path),'-o',str(out/(key+'.o'))]
    run=subprocess.run(command,capture_output=True,text=True)
    (out/(key+'.log')).write_text(run.stdout+run.stderr,encoding='utf-8')
    return dict(source=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                exit_code=run.returncode,object=key+'.o',
                errors=[s for s in run.stderr.splitlines() if 'error:' in s])

results=[]
if '--retry-failed' in sys.argv and (out/'results.json').exists():
    previous=json.loads((out/'results.json').read_text())
    successes={r['source']:r for r in previous['results'] if r['exit_code']==0}
    results=[successes[str(p)] for p in sources if str(p) in successes]
    sources_to_build=[p for p in sources if str(p) not in successes]
else:
    sources_to_build=sources
with ThreadPoolExecutor(max_workers=4) as pool:
    jobs=[pool.submit(build,p) for p in sources_to_build]
    for future in as_completed(jobs):
        results.append(future.result())
        if len(results)%40==0:print('Compiled',len(results),'of',len(sources),flush=True)
report=dict(source_count=len(sources),passed=sum(r['exit_code']==0 for r in results),results=results,
            linked=False,installed=False)
(out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
errors=Counter(s.split('error:',1)[-1].strip() for r in results for s in r['errors'])
print(json.dumps(dict(source_count=len(sources),passed=report['passed'],errors=errors),indent=2))
