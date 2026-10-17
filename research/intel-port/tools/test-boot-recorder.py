"""Exercise the recorder's real snapshot function, without Darwin or root writes."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

source = (Path(__file__).with_name('boot-recorder.sh')).read_text()
start = source.index('snapshot() {')
end = source.index('\n}\n', start) + 3
function = source[start:end]
bash = shutil.which('bash')
if not bash:
    raise SystemExit('This test requires Bash (the CI host provides it).')
with tempfile.TemporaryDirectory(prefix='cug-recorder-') as temporary:
    work = Path(temporary)
    script = work/'exercise.sh'
    script.write_text('set -eu\nOUT=$1\nCHILD=\n' + function + '''
snapshot fast printf 'first-buffer\n'
snapshot failure /bin/false
if snapshot blocked bash -c 'trap "" TERM; exec sleep 30'; then
    echo 'unexpected timeout success' >&2
    exit 1
fi
snapshot after printf 'recorder-continued\n'
''')
    began = time.monotonic()
    result = subprocess.run([bash, str(script), str(work)], capture_output=True,
                            text=True, timeout=15)
    elapsed = time.monotonic() - began
    assert result.returncode == 0, result.stdout + result.stderr
    assert (work/'fast.txt').read_text() == 'first-buffer\n'
    assert (work/'failure-exit.txt').read_text().strip() == '1'
    assert (work/'after.txt').read_text() == 'recorder-continued\n'
    assert 'timeout blocked' in (work/'progress.txt').read_text()
    assert not (work/'blocked-exit.txt').exists()
    assert elapsed < 12, elapsed
assert 'kmutil showloaded' not in source
assert source.index('snapshot "dmesg-$tick"') < source.index('snapshot "NMXGPU-$tick"')
assert '|| REGISTRY_OK=0' in source
print('PASS: fast and failed snapshots, TERM-resistant timeout, subsequent capture, and dmesg-first ordering.')
