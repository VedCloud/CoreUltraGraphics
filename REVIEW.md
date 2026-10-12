# Local source review — 2026-10-12

This records findings in the original supplied snapshot. Subsequent fixes supersede the probe/build/namespace findings: see docs/HARDWARE_BASELINE.md, docs/ARCHITECTURE.md and docs/TESTING.md. The experimental pipeline remains excluded from builds rather than made executable.

All 11 supplied files inspected. Original Downloads folder untouched; complete source snapshot preserved under workspace work/source-backup. No Git history or compiled kext supplied. Prior CI claims in comments are not independently verified.

## Findings

- Original injector overwrites its input without backup despite its non-destructive description. Fixed in this copy: mandatory new output, exclusive creation, structure validation, no ACPI changes, existing order retained, experimental kext disabled. No installation occurs. Candidate still contains original identifiers; keep it private.
- SSDT assumes _SB.PCI0.GFX0 exists and defines _DSM. A missing path or existing _DSM is a plausible namespace-error explanation, not a proven boot cause. Check original ACPI tables before loading it.
- Plist and SSDT specify 8086:7D45. This is an assumption, not a measured hardware ID.
- Driver derives from IOService and logs PCI/MMIO; it does not instantiate the execution pipeline or expose a Metal/framebuffer provider. Shader translation returns false. No acceleration implemented.
- Probe calls setMemoryEnable(true), changing the PCI command register without saving/restoring its original value. Thus it is not completely read-only. Bus mastering may already be enabled by firmware, contrary to the comment saying it stays off.
- Register offsets/power-well behavior remain unverified. Bounds checks do not establish register safety. Mapping-address logs should remain private.
- Pipeline uses CPU physical addresses where GPU mappings are required. Firmware, GPU VM, engine setup, scheduler and recovery are missing. Writes default off, but disabling the flag after init does not clear previously wired ring pointers; it is not a dependable runtime interlock.
- Public ring init multiplies unrestricted uint32_t size by four; needs allocation limits/overflow checks before broader use. Current call is 4096 dwords.
- Makefile/CI hardcode Xcode 15.4 and macOS 14.5 SDK. _kmod_info presence alone does not prove loadability or ABI correctness. No Apple SDK/compiler available here; C++ and ASL builds not performed.

## Validation

Run `python -m unittest -v test_inject_oc` and `python -m compileall -q inject_oc.py test_inject_oc.py`. Four offline tests cover unchanged input, ACPI preservation, disabled entry/order, overwrite rejection and malformed structures. These do not test a kext.

Use `python inject_oc.py COPIED_CONFIG --output NEW_CANDIDATE_PATH` to prepare a review file only. No actual EFI candidate created because USB files remain unreadable.

Boot diagnosis remains unresolved: E:/EFI and the specified log returned access denied after permission was granted. Required next evidence: workspace copies of EFI, SysReport and the full OpenCore log. Check whether this SSDT/kext is actually installed before connecting source findings to the failure.
