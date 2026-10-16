# Graphics build and validation

The `Core Ultra graphics and firmware validation` Actions workflow runs on
`graphics-firmware-build` pushes, selected pull requests, or manual dispatch.

It selects the active Xcode SDK and pins MacKernelSDK to
`3f750085caa17ec3a7880f11c11bf4f48cd6a164`. Both the C++ kext and C metadata
use kernel headers, and the link resolves against the matching x86_64 libraries.
The build fails if `_kmod_info` is absent, the artifact is not a thin x86_64
MH_KEXT_BUNDLE, or a test fails. Logs identify the exact source commit.

## Artifact

Download the successful run's `CoreUltraGraphics-diagnostic-<commit>` artifact.
It contains the kext ZIP, toolchain/build logs, test output, symbol inspection,
binary hash, firmware provenance manifest and retained firmware license.
Failed runs preserve available diagnostic logs and do not create a success ZIP.
The referenced firmware is downloaded for offline tests, not embedded in the kext.

The 0.3.0 driver matches 8086:7D45 and publishes
`CoreUltraGraphicsAccelerationSupported = false`. It inspects PCI configuration
and existing resource descriptors, then attempts two allowlisted identification
reads using a temporary uncached, read-only BAR0 mapping. It checks PCI D0,
memory decode, resource identity and bounds before reading. It never enables
decode, writes MMIO, requests forcewake or allocates DMA. See [MMIO scope](MMIO_PROBE.md).
The separate match category allows a diagnostic service alongside other categories.
Building and inspecting
it in Actions is not a load/boot test. The workflow does not modify an EFI,
load a kext, upload firmware to hardware or claim GPU acceleration.

## Firmware reference

The supplied Linux reports identify GuC 70.53.0, HuC 8.5.4 and GSC
102.1.15.1926. Reference blobs are fetched unmodified from linux-firmware commit
`38c1a7096dfb2188f55f342b835f14c362c59409`, verified against Git object hashes,
and kept outside Git. No private report or raw trace is published here.
The repository contains original offline parsers and source-derived codecs,
not a decompilation of the firmware's internal instructions.

The recorded i915 capture contains fourteen complete observed GuC setup requests
across render/media channels, followed by success headers. It also reports
1,823,992 kernel overruns, so the initialization trace is incomplete. Its G2H
buffer size is 16 KiB; the earlier Xe reference uses 128 KiB. Captured addresses
must not be replayed in another OS or address space.

## Reproduce on macOS

```sh
python3 research/tools/fetch_mtl_firmware.py
python3 -m unittest test_verify_kext -v
(cd research && python3 -m unittest discover -s tests -v)
clang -std=c11 -Wall -Wextra -Werror tests/test_c_batch.c -o /tmp/cug-mi-test
/tmp/cug-mi-test
clang -std=c11 -Wall -Wextra -Werror tests/test_guc_protocol.c -o /tmp/cug-guc-test
/tmp/cug-guc-test
clang -std=c11 -Wall -Wextra -Werror tests/test_mmio_probe.c -o /tmp/cug-mmio-test
/tmp/cug-mmio-test
make KERNEL_SDK=/absolute/path/to/MacKernelSDK
python3 verify_kext.py CoreUltraGraphics.kext
```

Next hardware milestone: verify the returned GMD identification values. Later:
owned GPU memory mappings, interrupt/reset handling,
firmware validation/load/authentication and a bounded GuC transport handshake.
Command execution and native macOS graphics integration remain additional work.

## Linux REA inspection

On branch pushes, an additional Ubuntu job installs Binwalk 3.1.0 and REA 6.5.0
in the disposable runner, then invokes REA's real firmware-signature inspector
on the three matching GuC/HuC/GSC images. It retains complete evidence, stderr,
tool versions, a dependency lock, and firmware hashes in a separate artifact.
This is signature/region inspection, not firmware instruction decompilation or
hardware execution. It does not change the user's Codex configuration.
