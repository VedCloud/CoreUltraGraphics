# Intel GuC and framebuffer source candidate

This directory contains an experimental source overlay for the NullMoth i915
port, focused on Intel 8086:7D45. **It is not a hardware-validated Metal driver.**

## Implementation

`port/nullmoth-candidate/nmx_i915_bridge.c` implements a validated GuC policy setter
and a CPU-mappable GGTT scanout mapping. It holds VMA/mapping/runtime-power
references, checks aperture arithmetic, rejects a wedged GT and unwinds failures.

The overlay integrates that helper into the generic framebuffer bridge and adds
the `nmxguc` boot-option hook before port initialization. It also withholds the
accelerator claim if framebuffer publication fails. The build restricts the
candidate to Intel 7D45; AMD and Xe are not linked into this candidate.

`nmxguc` accepts 0–3. Mode 2 requests HuC loading and requires GuC; mode 3 also
requests GuC submission. The hook is not present in the old released binary.
Do not assume these options make existing USB payloads behave differently.

## Local validation

* 24 cases run the actual mapping/control-flow code with fault-injected kernel
  doubles, covering cleanup, lock retries, invalid policy and bounds.
* All 65,536 16-bit inputs check the constant-bitcount compatibility helpers.
* 273 selected i915 units and 163 selected DRM/runtime/glue units compile to
  x86-64 Mach-O objects against real pinned headers.
* Several structure offsets agree with the inspected released binary. This is
  supporting evidence, not a universal private-ABI guarantee.

See [the sanitized build summary](validation/local-build-summary.json) and
[the hardware report](../../reports.md).

## Reproduce host tests

Requires Python 3 and clang (the local workspace can alternatively use its bundled Zig).

```sh
python3 research/intel-port/tools/test-intel-bridge.py
```

The test fixture replaces kernel APIs, not the production control flow. Passing it
does not establish a Mac kernel load or hardware execution.

## Rebuild on macOS/Xcode

Run from the repository root. The fetcher downloads roughly 55 MB of pinned
archives plus 415 individually hash-checked LinuxKPI headers. Generated sources,
objects and logs stay inside this directory and are ignored by Git.

```sh
python3 research/intel-port/tools/fetch-intel-build-inputs.py
python3 research/intel-port/tools/prepare-intel-bridge-overlay.py
python3 research/intel-port/tools/compile-intel-bridge.py nmx_i915_bridge.c
python3 research/intel-port/tools/compile-intel-bridge.py nmx_fb_bridge.c
python3 research/intel-port/tools/compile-intel-bridge.py nmx_kext.cpp
python3 research/intel-port/tools/compile-intel-bridge.py layout-probe.c
python3 research/intel-port/tools/compile-intel-driver.py
python3 research/intel-port/tools/compile-intel-runtime.py
python3 research/intel-port/tools/link-intel-port.py
```

`compile-intel-driver.py --retry-failed` and the corresponding runtime option are
local incremental helpers; use a clean build for release/artifact provenance.
The final linker checks that every selected source unit compiled, requires
`_kmod_info`, restricts PCI matching and rejects unresolved internal port symbols.
The linked output, if successful, is in `evidence/intel-linked-build/`.

The [Actions workflow](https://github.com/VedCloud2/CoreUltraGraphics/actions/workflows/intel-port.yml)
performs a clean macOS build and retains logs on failure. The Windows source-build
toolchain cannot emit Apple's final `-kext` format. A failed Actions link must not
be presented as a completed kext build.

No tool here installs a kext, changes EFI, writes GPU registers on the host, rebuilds
a running Mac's kernel collection or reboots a machine. Installation and native
Metal testing remain separate hardware steps after a concrete artifact is reviewed.

## Input identity

| Input | Pin |
| --- | --- |
| GPU port | `277a29bea10371a88c4c1fb104409060d31962e8` |
| drm-kmod | `c16de0f9fa84f70b9551f69fde837a7f3a73c0e9` |
| Supplemental LinuxKPI headers | `bdcfeac3e1cb8ce3f05c32d8a7ad3597deb48bdf` |
| MacKernelSDK | `3f750085caa17ec3a7880f11c11bf4f48cd6a164` |
| NPU runtime source archive | SHA256 `9dd7c229e1e05cb6c574dfc7623cc3d467f84eb9f39ab4913203a36aaf1d4747` |

Archive hashes are enforced by the fetcher; header hashes are in
[`pins/linuxkpi-headers.json`](pins/linuxkpi-headers.json).

## Licences

The included NullMoth-derived overlay sources and patches are subject to the
upstream [PolyForm Noncommercial 1.0.0 terms](LICENSE.NULLMOTH.txt). New standalone
helper files carry their own MIT SPDX notices; that does not relicense the
upstream port or the linked combined work. Intel/DRM/FreeBSD/Apple inputs retain
their upstream notices and terms. The NPU archive includes its own notices.

This repository does not redistribute firmware or the upstream Metal plug-in as
part of this source overlay. See [repository third-party notices](../../THIRD-PARTY-LICENSES.md).
