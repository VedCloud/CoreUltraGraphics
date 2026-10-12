# Measured Latitude baseline — 2026-10-12

Source: user-provided offline Linux report ZIP in Desktop/REPORTS, corroborated by Windows PCI enumeration. ZIP SHA-256: 373415bdaa419009d139372baf64c4d8de53199781c31fac36a0bbcaa15f27d4. File integrity is recorded; collector provenance and all summary assertions are not independently certified. Raw reports remain private and are not bundled with project source.

| Item | Observed evidence |
|---|---|
| System | Dell Latitude 5350, Core Ultra 5 135U |
| GPU | Vendor 8086, device 7D45, revision 08; report PCI config bytes agree with report JSON and Windows registry |
| Graphics/media/display | i915 capabilities: graphics 12.70, media 13; dmesg: display 14.00 |
| Execution topology | 64 EUs, 4 subslices; 48-bit PPGTT and 46-bit DMA mask reported |
| ACPI GPU | `\_SB_.PC00.GFX0`; OpenCore device path reported as `PciRoot(0x0)/Pci(0x2,0x0)` |
| Kernel | Collector reports Linux 6.18.53-0-lts, Alpine build |
| Display | eDP-1 connected/enabled, pipe A, 1920x1080 at 60 Hz; additional 48 Hz panel mode |
| Link | 2 lanes, port clock 270000 kHz in display dump |
| Panel | BOE product 0BAE; no panel serial exported |
| BAR sizes | BAR0 16 MiB and BAR2 256 MiB, both reported 64-bit and above 4 GiB; addresses omitted |
| Storage | KIOXIA BG6 512 GB, firmware 12000105; serial omitted |
| BIOS | 1.23.0; collector reports CFG Lock locked and Secure Boot off; no settings changed |

Observed firmware from post-driver dmesg:

- DMC: i915/mtl_dmc.bin, version 2.23.
- GuC: i915/mtl_guc_70.bin, version 70.53.0, GT0 and GT1; submission/SLPC/RC enabled.
- HuC: i915/mtl_huc_gsc.bin, version 8.5.4; clear-media and later all-workloads authentication reported.
- GSC: i915/mtl_gsc_1.bin, reported release 102.1.15.1926. Missing MEI component/GSC proxy initialisation errors also present.

These are observed versions in this collector session, not automatically recommended versions for a new driver. Firmware binaries were not present in the archive, downloaded or redistributed.

The Linux stack initialised and drove a framebuffer. No render/compute known-output workload or benchmark is included, so successful GPU rendering is not claimed. NPU firmware-request errors concern intel_vpu, not proof of an iGPU failure.

39 standard ACPI tables passed declared-length and checksum checks; FACS excluded from the standard checksum test. This does not establish namespace correctness. DSDT and 23 SSDTs are available for later real decompilation. No iasl tool was available in this session and no AML execution occurred.

Collector summary says "UEFI GOP no", but its boot framebuffer record and dmesg show simpledrm before i915. Treat that summary flag as collector-specific detection, not evidence that firmware output is absent. Do not derive a macOS boot diagnosis from it.
