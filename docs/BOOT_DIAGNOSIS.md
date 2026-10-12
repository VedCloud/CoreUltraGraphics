# Boot diagnosis update

Confirmed source mismatch: SSDT-GFX0.asl targeted _SB.PCI0.GFX0; the supplied hardware report identifies _SB.PC00.GFX0. Corrected the source path in the reviewed copy. The source remains excluded from automatic injection. No compiled AML or EFI was changed.

Important uncertainty: existing EFI may rename PC00 to PCI0, may already define _DSM, or may not load this overlay at all. Therefore this is a real source/report discrepancy, not yet a verified cause of the macOS failure. Decompile the original tables with their external dependencies and inspect actual OpenCore patches before using a revised overlay. The measured native PCI ID already matches the kext, so GPU-ID injection has no demonstrated purpose here.

The reported CFG Lock is a CPU/power-management consideration for the actual configuration audit. It does not justify firmware modification or a guessed quirk change. Neither the VirtualSMC message nor ACPI-error paraphrase establishes a fatal blocker.

Missing evidence: current EFI/config.plist and full macOS/OpenCore boot log remain inaccessible at E:. The supplied REPORTS archive contains Linux evidence, ACPI tables, VBT/OpRegion/EDID and PCI data, but no OpenCore configuration or macOS panic. Root cause is still unresolved.
