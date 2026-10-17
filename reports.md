# Graphics investigation reports

Updated 17 October 2026. Target: Dell Latitude 5350, Core Ultra 5 135U,
Intel 8086:7D45 rev08, graphics IP 12.70 / media IP 13.00, macOS Sequoia.

**No hardware-accelerated Metal validation has passed on this laptop.** The new
milestone is source implementation and successful object compilation, not a
corrected hardware boot.

## Evidence and timeline

Raw archives remain on the local test USB. This public report publishes relevant
findings and hashes rather than complete machine-specific dumps.

| Stage | Observation | What it establishes |
| --- | --- | --- |
| Working Linux report, 12 October | i915 recognizes MTL; GuC submission/SLPC and HuC authentication appear | GPU works with Linux's stack |
| macOS diagnostic probe | PCI identity and bounded read-only identification | Probe behavior, not rendering |
| Early NMX installs | Kernel-collection records pointed to deleted temporary staging paths | Installer/KC defect |
| Permanent-path KC repair | NMX records built from `/Library/Extensions` | Corrected collection provenance, not GPU execution |
| PCI matcher investigation | Overlapping Xe/i915 tables could choose the wrong registered driver | Reproduced matcher defect |
| DP tunnel investigation | Feature/configuration mismatch returned `-102` during probe | Reproduced unsupported optional-feature path |
| Latest failed USB boot, 00:31:07 | MTL recognized, DMC loaded, DRM registered; GT0 wedged and scanout failed | Earlier probe blockers passed; graphics still failed |
| New source candidate | GuC hook and GGTT scanout implementation compile | Source/build progress; hardware test pending |

## Latest hardware failure: 20261017-003313

Archive: `Intel-failed-boot-20261017-003313.tar.gz`

SHA256: `67ae86ae00e1e2d753a34e2e8d2b205a397a5d6f5c0a74040b9dbbcda6d1214c`

The relevant boot is the 00:31:07 sequence; earlier timestamps retained in the
persisted log belong to other attempts.

```text
GT0: Enabling uc failed (-5)
GT0: Failed to initialize GPU, declaring it wedged!
GT0: Non-recoverable wedged on init
NullMoth display: the scan-out buffer would not map (102)
NullMoth display: no framebuffer (102)
```

NMXAccel subsequently registered a service, but its display sweep found zero
framebuffers and WindowServer failed framebuffer initialization. Service names and
the black screen do not establish rendering or Metal execution.

### GuC policy

All original/matcher/probe binary variants have `i915_modparams.enable_guc=0` at
virtual/file address `0xccf10c`. Disassembly confirms the parameter copy to
i915+`0x2148` and reads at i915+`0x214c`.

The port retains FreeBSD's disabled GuC default. Its loader-tunable fetches are
no-ops on macOS; Linux/FreeBSD argument names added to OpenCore have no demonstrated
effect on that binary. The disabled-path hardware check can return `-EIO` for an
invalid firmware table or locked/valid WOPCM state. Physical WOPCM values were not
captured, so the exact branch remains unconfirmed. No GuC upload success is shown.

The source candidate adds a real `nmxguc` option before initialization, validates
values 0–3, and retains the existing errors/checks. Mode 2 is a FreeBSD bring-up
reference; mode 3 also requests GuC submission. Neither has passed a new Mac test.

### Framebuffer mapping

The generic bridge calls GEM vmap, but the actual i915 callback slot at `0xc797c8`
is NULL. The helper returns `-102`, logged as positive 102 after negation. This
directly explains the mapping error.

The new Intel path pins a CPU-mappable GGTT VMA, validates the physical aperture,
holds the mapping/power/object references, and releases them on teardown. It checks
that the CPU view matches the published range and rejects a wedged GT. Generic
mapping remains available for other drivers.

The FreeBSD GMADR patch is not additionally missing from our released binary path:
MTL device-info byte `0x41` takes BAR2 validation and GMADR initialization. Actual
resource values still need hardware logging. MTL's stolen-memory workaround is
retained; forcing contiguous stolen RAM is not the mapping repair.

## Binary provenance

| Artifact | SHA256 |
| --- | --- |
| Original NMXGPU package binary | `0f9108a814acb480ba1859bf13f1d01ac948039f0e3158bf45ea1850012c181c` |
| Matcher workaround | `9f903b7ed5b007ca12c3e23094137f771070b45f4fbee4aab9d85615f78d31f5` |
| Matcher + DP tunnel workaround used by the latest failure | `a931d61b2082108f1cb968fc14e0f6a9cfaeaeb961646909db40e3316edfa315` |

These are older binary artifacts, not the new source-build candidate. A newly
linked candidate requires its own hash and separate hardware result.

## Source/build results

| Input | Pin |
| --- | --- |
| NullMoth port | `277a29bea10371a88c4c1fb104409060d31962e8` |
| FreeBSD drm-kmod | `c16de0f9fa84f70b9551f69fde837a7f3a73c0e9` |
| Supplemental FreeBSD LinuxKPI headers | `bdcfeac3e1cb8ce3f05c32d8a7ad3597deb48bdf` |
| MacKernelSDK | `3f750085caa17ec3a7880f11c11bf4f48cd6a164` |

The NPU runtime archive alone is not the complete GPU build. The fetcher combines
these pinned trees, the runtime archive and 415 hash-checked supplemental headers.
Private driver structure compatibility is checked, not assumed for arbitrary trees.

| Check | Local result | Limitation |
| --- | --- | --- |
| Original failure reproduction | 8 assertions pass | Simulated registers/APIs |
| Production bridge control flow | 24 cases pass | Kernel API doubles |
| Bitcount helpers | 65,536 inputs checked | Portable semantics |
| i915 source units | 273 / 273 compile | Object compilation only |
| DRM/runtime/glue units | 163 / 163 compile | Object compilation only |
| Local final kext link | Windows Zig rejects `-kext` | macOS/Xcode used instead |
| macOS full source build | 273 + 163 units compile | Clean build in run 39032198815 |
| macOS final link and inspection | Pass in run 39032518254 | No hardware execution implied |
| Native Metal compute check | Not passed | Hardware acceptance required |

The rebuild also repairs missing constant-bitcount/qsort declarations and older
kernel-SDK string typing. These build repairs do not establish acceleration.

See [build instructions](research/intel-port/README.md),
[local validation summary](research/intel-port/validation/local-build-summary.json),
and [macOS Actions logs](https://github.com/VedCloud2/CoreUltraGraphics/actions/workflows/intel-port.yml).

## Installation and next acceptance

The installer must build the final auxiliary collection after payload installation
and inspect permanent `/Library/Extensions` references. Temporary staging paths
must not be published. FAT32 backup writes must not depend on unsupported file flags.
Installer/KC success is separate from GPU initialization and Metal success.

No new source candidate has been installed into the USB EFI in this report. The
working SSD EFI is separate, and VoodooI2CHID is unchanged by this graphics work.

The linked candidate is available from
[run 39032518254](https://github.com/VedCloud2/CoreUltraGraphics/actions/runs/39032518254).
Binary SHA256: `3ed1770f0e61945c4501459b44ed49e3cfcacde3e861b78f69a70fa160825df9`.
Artifact archive SHA256: `6f426e248e63006da00b8bf6fade201b631f18d49120d74be53bd7e01a53512a`.
The link reused the passing macOS compilation with source-hash verification.
The first link attempt failed because kernel runtime library search paths were
missing; adding the pinned SDK paths and macOS sysroot resolved it.

The guarded installer stages the candidate while the old driver is parked with
`-nvoff`, backs up binary/metadata/collection/configuration, checks permanent KC
paths and activates the new USB configuration last. Mac installation and the
hardware boot have not been observed yet.

The next hardware record must name the artifact and SHA256, effective GuC
policy, initialization/wedge state, valid framebuffer dimensions/range,
WindowServer result, and completed native Metal checker output.

## Primary sources

* [Linux uC initialization](https://github.com/torvalds/linux/blob/v6.14/drivers/gpu/drm/i915/gt/uc/intel_uc.c)
* [DRM GEM mapping](https://github.com/torvalds/linux/blob/v6.14/drivers/gpu/drm/drm_gem.c)
* [FreeBSD GuC defaults](https://github.com/freebsd/drm-kmod/blob/c16de0f9fa84f70b9551f69fde837a7f3a73c0e9/drivers/gpu/drm/i915/i915_params.h)
* [Same-device FreeBSD report](https://github.com/freebsd/drm-kmod/issues/441), including Vulkan stress hangs
* [GMADR change](https://github.com/freebsd/drm-kmod/commit/a2ca1d53b57318ceee2489674441cbb6458ad659)
* [Intel CPU framebuffer mapping reference](https://github.com/freebsd/drm-kmod/blob/c16de0f9fa84f70b9551f69fde837a7f3a73c0e9/drivers/gpu/drm/i915/display/intel_fbdev_fb.c)
