# CoreUltraGraphics

Experimental Intel Meteor Lake graphics bring-up on **macOS Sequoia**, focused on
the **Dell Latitude 5350 / Core Ultra 5 135U / Intel 8086:7D45 rev08**.

**Hardware-accelerated Metal has not been verified. There is no hardware-validated
accelerated EFI or replacement graphics driver ready for installation.** A loaded
accelerator service, DMC message, successful build or black screen does not prove
that GPU rendering works.

## Status — 17 October 2026

| Component | Purpose | Current evidence |
| --- | --- | --- |
| `CoreUltraGraphics.kext` 0.3.0 | Read-only PCI/GMD_ID identification probe | Diagnostic only; no GPU initialization or Metal implementation |
| Intel port candidate | Adapt the existing NullMoth/FreeBSD/LinuxKPI i915 stack | GuC option and GGTT framebuffer mapping implemented in source; 436 selected units compile locally |
| Upstream NMXAccel / ANV / Metal plug-in | Experimental user-space/accelerator stack used by the test kit | No successful native Metal compute result on this laptop |

The source rebuild compiles **273 i915 units and 163 DRM/LinuxKPI/XNU/IOKit units**
to x86-64 Mach-O objects. The macOS Actions build also compiled all 436 units and
**successfully linked and inspected an Intel-only kext** in
[run 39032518254](https://github.com/VedCloud2/CoreUltraGraphics/actions/runs/39032518254).
Its binary SHA256 is `3ed1770f0e61945c4501459b44ed49e3cfcacde3e861b78f69a70fa160825df9`.
Hardware loading and usability are still unverified.

**[Read reports.md](reports.md)** for the hardware timeline, evidence hashes,
precise failures, source repairs and remaining acceptance checks.

## What failed on hardware

The latest investigated report, `Intel-failed-boot-20261017-003313.tar.gz`, shows
that earlier PCI-matcher and optional-DP-tunnel workarounds allowed i915 to identify
Meteor Lake, load DMC 2.23 and register DRM. Two independent failures remained:

1. GT0 reported `Enabling uc failed (-5)` and became wedged. The released binary
   has `enable_guc=0`; successful GuC loading was not established.
2. Scanout mapping returned `102`. The bridge called a generic GEM mapping callback
   that i915 does not implement, published no framebuffer, and WindowServer failed.

The black screen was a failure symptom, not proof of acceleration.

## Source changes now implemented

The candidate lives in [research/intel-port](research/intel-port/README.md).

* Apply a validated `nmxguc` boot option to i915 before initialization. Linux or
  FreeBSD parameter spellings alone do not configure this macOS port.
* Use a CPU-mappable, pinned **GGTT aperture** for Intel scanout, with checked
  physical bounds and complete mapping/power/reference cleanup.
* Reject a wedged GT and preserve microcontroller errors instead of suppressing them.
* Publish the framebuffer before advertising the accelerator claim.
* Build an Intel-only candidate, restricted to 7D45, avoiding the earlier Xe/i915
  registration collision. Keep optional unsupported DP tunnelling disabled.

These changes compile but have not passed a new corrected hardware boot. The older
binary workarounds and the new source candidate are different artifacts.

## Validation

| Check | Result | Scope |
| --- | --- | --- |
| Original uC/GEM failure reproduction | 8 assertions pass | Extracted upstream C with simulated registers/APIs |
| New production bridge control flow | 24 cases pass | Allocation/mapping failures, lock retry, cleanup, policy and bounds |
| Bitcount compatibility | 65,536 inputs checked | Portable helper semantics |
| i915 compilation | 273 / 273 units | Real pinned headers; object compilation |
| DRM/runtime/glue compilation | 163 / 163 units | Real pinned headers; object compilation |
| macOS final kext link and inspection | Passed in run 39032518254 | 436 objects; `_kmod_info` and internal symbols checked |
| Native Metal output validation | Not passed | Required hardware milestone |

See [machine-readable local results](research/intel-port/validation/local-build-summary.json).
The detailed structure/layout checks support the source selection but do not make
private driver ABIs interchangeable with every upstream revision.

## Build and inspect

```sh
python3 research/intel-port/tools/test-intel-bridge.py
python3 research/intel-port/tools/fetch-intel-build-inputs.py
python3 research/intel-port/tools/prepare-intel-bridge-overlay.py
```

The host tests need Python 3 and clang. See the [Intel port build guide](research/intel-port/README.md)
for the macOS/Xcode compilation/link steps, input pins and artifact limitations.

* [Intel port Actions workflow](https://github.com/VedCloud2/CoreUltraGraphics/actions/workflows/intel-port.yml)
* [Diagnostic graphics workflow](https://github.com/VedCloud2/CoreUltraGraphics/actions/workflows/graphics-firmware.yml)
* [Existing diagnostic build instructions](https://github.com/VedCloud2/CoreUltraGraphics/blob/graphics-firmware-build/docs/BUILD_AND_TEST.md)
* [Read-only MMIO probe scope](https://github.com/VedCloud2/CoreUltraGraphics/blob/graphics-firmware-build/docs/MMIO_PROBE.md)

A CI artifact is not installed automatically and is not a compatibility certification.

## Hardware acceptance still required

1. Install the inspected artifact using the guarded parked-USB test procedure.
2. Build a kernel collection from permanent installed kext paths.
3. Observe effective GuC policy, successful firmware initialization and an unwedged GT.
4. Publish a valid framebuffer and reach a usable WindowServer desktop.
5. Complete the native Metal compute checker on 8086:7D45 and validate its output.
6. Exercise workloads, repeated boots, sleep/wake and display changes.

The working SSD EFI is separate from the USB experiments. This source work does
not change it. VoodooI2CHID remains outside the graphics fix scope. The USB uses
its mapped USBToolBox/UTBMap configuration; UTBDefault was removed separately.

## Repository layout

| Path | Contents |
| --- | --- |
| `CoreUltraGraphicsDriver.*` | Diagnostic PCI/MMIO probe |
| `port/`, `tests/` | Portable diagnostic/protocol work on the graphics branch |
| `research/intel-port/` | Source overlay, dependency pins, tests and build tooling |
| `scripts/intel-test/` | Experimental installation/rollback scripts on the graphics branch |
| `meteor-gpio/` | Separate GPIO/peripheral work; not Metal acceleration |
| `reports.md` | Curated hardware and build findings |

The default branch also contains peripheral work. Graphics development remains on
[`graphics-firmware-build`](https://github.com/VedCloud2/CoreUltraGraphics/tree/graphics-firmware-build).
The dormant `XeTranslationPipeline` is excluded from the diagnostic build; its
unimplemented translation and old ring/display paths are not this fix.

## Upstream work and licences

This effort reuses [Linux i915](https://github.com/torvalds/linux/tree/master/drivers/gpu/drm/i915),
[FreeBSD drm-kmod](https://github.com/freebsd/drm-kmod), the pinned
[NullMoth port](https://github.com/nullmoth/nvidia-macos-driver/tree/277a29bea10371a88c4c1fb104409060d31962e8)
and [MacKernelSDK](https://github.com/acidanthera/MacKernelSDK).
The [same-device FreeBSD report](https://github.com/freebsd/drm-kmod/issues/441)
provides GuC/display bring-up clues but also reports Vulkan stress hangs.

This is not a completed reverse engineering of GuC's instruction set or a newly
implemented Metal driver. Firmware-container and host-protocol analysis are
separate from functioning acceleration. See [third-party notices](THIRD-PARTY-LICENSES.md)
and the [port licence notes](research/intel-port/README.md#licences).
