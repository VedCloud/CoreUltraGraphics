"""Compile the candidate against pinned real i915, LinuxKPI and XNU headers.

Produces a Mach-O object only, never installs or links it into the released kext.
"""
from pathlib import Path
import json
import subprocess
import sys
import shutil

root = Path(__file__).resolve().parents[1]
inputs = root / 'tooling/build-inputs'
x = root / 'upstream/nmxnpu-source-2.1.0/nmxnpu-source/xkpi'
public = inputs/'nvidia-macos-driver-277a29bea10371a88c4c1fb104409060d31962e8/gpu-port/xkpi'
l = x.parent / 'upstream/kpi/freebsd-src/sys/compat/linuxkpi'
d = inputs / 'drm-kmod-c16de0f9fa84f70b9551f69fde837a7f3a73c0e9'
k = inputs / 'MacKernelSDK-3f750085caa17ec3a7880f11c11bf4f48cd6a164/Headers'
source_name = sys.argv[1] if len(sys.argv) > 1 else 'nmx_i915_bridge.c'
assert source_name in ('nmx_i915_bridge.c', 'nmx_fb_bridge.c', 'nmx_kext.cpp', 'layout-probe.c')
out = root / 'evidence/intel-bridge-build'
out.mkdir(parents=True, exist_ok=True)
command = [str(root / 'tooling/re-tools/ziglang/zig.exe'), 'cc', '-target', 'x86_64-macos',
           '-mmacosx-version-min=15.0', '-mkernel', '-fapple-kext', '-nostdinc', '-std=gnu11',
           '-fno-builtin', '-fno-common', '-fno-strict-aliasing', '-fms-extensions', '-O2',
           '-Wno-pointer-sign', '-Wno-unused-parameter', '-Wno-microsoft-anon-tag', '-ferror-limit=12',
           '-D_KERNEL', '-DKERNEL', '-DKERNEL_PRIVATE', '-DLINUXKPI_VERSION=61400', '-DNMXKPI=1', '-DI915']
for pre in [public/'bsdcompat/include/nmxkpi_prelude.h', l/'common/include/linux/compiler_types.h',
            l/'common/include/linux/kconfig.h', public/'bsdcompat/include/nmxkpi_post.h',
            root/'port/nullmoth-candidate/nmx_bitcount_compat.h']:
    command += ['-include', str(pre)]
includes = [public/'override/include', public/'bsdcompat/include',
            d/'linuxkpi/bsd/include', l/'common/include', l/'dummy/include',
            inputs/'freebsd-linuxkpi-full/common/include', inputs/'freebsd-linuxkpi-full/dummy/include',
            x/'fbroot', d/'include', d/'include/drm',
            d/'include/uapi', d/'drivers/gpu/drm', d/'drivers/gpu', d/'drivers',
            d/'drivers/gpu/drm/i915', d/'drivers/gpu/drm/i915/display',
            d/'drivers/gpu/drm/i915/gem', k, root/'port/nullmoth-candidate']
for directory in includes:
    command += ['-I', str(directory)]
for flag in (x/'amd.flags').read_text().splitlines():
    if flag and not any(s in flag for s in ['KBUILD_MODNAME', 'PARAM_PREFIX', '/drm/amd', 'CONFIG_DRM_I915_DP_TUNNEL']):
        command.append(flag)
command += ['-DKBUILD_MODNAME="i915kms"', '-DLINUXKPI_PARAM_PREFIX=i915_',
            '-DDRM_SYSCTL_PARAM_PREFIX=_i915kms', '-c',
            str(root/'port/nullmoth-candidate'/source_name), '-o', str(out/(Path(source_name).stem+'.o'))]
if source_name.endswith('.cpp'):
    command = [str(root/'tooling/re-tools/ziglang/zig.exe'), 'c++', '-target', 'x86_64-macos',
               '-mmacosx-version-min=15.0', '-mkernel', '-fapple-kext', '-nostdinc',
               '-std=c++17', '-fno-rtti', '-fno-exceptions', '-fno-builtin', '-fno-common', '-O2',
               '-DKERNEL', '-DKERNEL_PRIVATE', '-DDRIVER_PRIVATE', '-DAPPLE', '-DNeXT',
               '-I', str(k), '-I', str(x/'bsdcompat/include/nmxxnu'),
               '-I', str(root/'port/nullmoth-candidate'), '-c',
               str(root/'port/nullmoth-candidate'/source_name), '-o', str(out/(Path(source_name).stem+'.o'))]
if sys.platform == 'darwin':
    language = 'clang++' if source_name.endswith('.cpp') else 'clang'
    native = subprocess.check_output(['xcrun', '--find', language], text=True).strip()
    command = [native] + command[2:]
    command[command.index('x86_64-macos')] = 'x86_64-apple-macos15.0'
run = subprocess.run(command, capture_output=True, text=True)
(out/(source_name+'.compile.log')).write_text(run.stdout+run.stderr, encoding='utf-8')
(out/(source_name+'.compile-command.json')).write_text(json.dumps(command, indent=2)+'\n')
print('\n'.join(line for line in (run.stdout+run.stderr).splitlines() if 'error:' in line))
print('exit_code:', run.returncode)
sys.exit(run.returncode)
