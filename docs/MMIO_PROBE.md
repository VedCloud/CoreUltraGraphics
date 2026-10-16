# Read-only GMD identification probe 0.3.0

The prior 0.2.0 metadata probe attached to the measured 8086:7D45 revision 08
provider with the existing framebuffer and class mask. Version 0.3.0 takes
the next step: exactly two 32-bit identification reads during driver start.

| Read | BAR0 byte offset | Decoded fields |
| --- | --- | --- |
| Graphics GMD_ID | 0x00000d8c | architecture [31:22], release [21:14], revision [5:0] |
| Media GMD_ID | 0x00380d8c | same |

Only these offsets are permitted by the portable policy. No GuC status, WOPCM,
GGTT, engine, interrupt, reset, or display register is accessed. No firmware
is transferred. Graphics acceleration and Metal remain unimplemented.

## Source basis

Historical baseline: Linux v6.12 commit
`adc218676eef25575469234709c2d87185ca223a`, matching the research baseline.
These are source-derived register facts, not a firmware decompilation.

- [xe_gt_regs.h](https://github.com/torvalds/linux/blob/adc218676eef25575469234709c2d87185ca223a/drivers/gpu/drm/xe/regs/xe_gt_regs.h)
  defines GMD_ID, its fields and MEDIA_GT_GSI_OFFSET = 0x380000.
- [xe_pci.c read_gmdid](https://github.com/torvalds/linux/blob/adc218676eef25575469234709c2d87185ca223a/drivers/gpu/drm/xe/xe_pci.c)
  performs early reads, explicitly adding the media offset before GT setup.
- [intel_uncore.c __mtl_fw_ranges](https://github.com/torvalds/linux/blob/adc218676eef25575469234709c2d87185ca223a/drivers/gpu/drm/i915/intel_uncore.c)
  assigns no forcewake domain to 0xc00..0xfff and 0x380c00..0x380fff.
- [xe_mmio.c](https://github.com/torvalds/linux/blob/adc218676eef25575469234709c2d87185ca223a/drivers/gpu/drm/xe/xe_mmio.c)
  identifies BAR0 as the register/GGTT aperture. This probe does not access GGTT.

## Access and lifetime

Read PCI configuration first: memory decode must already be enabled and PMCSR
must report D0. Unknown/missing power capability or non-D0 skips the reads.
The BAR0 value must describe a 64-bit memory BAR, match the IOKit resource's
physical address, and have the measured 16 MiB length. Physical addresses are
discovered on each boot; none are embedded in the code.

Use IOPCIDevice's BAR-register mapping API with kIOMapInhibitCache and
kIOMapReadOnly. Validate its physical identity, virtual address, lengths and
PCI power/decode again before two volatile little-endian loads. Release the
mapping immediately, including when post-map checks fail. There is no retained
mapping, timer, work loop, user client, or sleep/wake register access.

This is a boot-time experiment. PCI D0 checks do not implement full macOS
runtime power coordination or prove power cannot change between observations.
The source evidence supports these particular early identification reads;
it must not be generalized to arbitrary GT registers or GuC accesses.

## Interpreting a returned report

`CoreUltraGraphicsProbeVersion = 0.3.0` identifies this build.
`ProbeMMIOReadCount = 2` and status `attached; GMD identification read` indicate
both values passed basic sanity checks. Raw zero/all-ones or architecture zero
are marked invalid; a plausible value is not proof of correct initialization.
Read `ProbeGraphicsGMDRaw` / `ProbeMediaGMDRaw` and the Architecture, Release,
Revision properties. A skipped status provides the failed prerequisite.
`ProbeMMIOMappingActive = false` means the temporary mapping has been released.
`ProbeMMIOWritesPerformed = false`, `ProbeForcewakeRequested = false` and
GuCInitialized/AccelerationSupported false describe this build's scope.

Offline C tests cover access bounds, excluded registers, malformed values and
known field decoding under ASan/UBSan. CI also builds the actual kernel code;
neither check substitutes for a laptop boot and returned collector report.
