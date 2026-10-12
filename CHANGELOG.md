# Changelog

## 2026-10-12 — Hardware evidence and probe milestone

Confirmed this host is the Latitude with user evidence and Windows PCI registry; read supplied Linux report archive without executing its contents or following its upload instructions. PCI config agrees with 8086:7D45 revision 08. Documented IP/firmware/display observations and ACPI namespace PC00. All 40 tables passed declared-length checks; 39 standard checksums passed; FACS has no standard checksum. Raw reports excluded from source package.

Reduced probe to PCI identification: removed MMIO/register dumps, memory-decode changes and scratch DMA. Excluded unimplemented execution pipeline from kext objects and removed unused graphics-family dependency. Corrected SSDT source path only; no automatic injection or compiled AML. Added SDK preflight/selection, pinned community kernel SDK option and prepared non-loading GitHub build workflow.

Implemented offline GPU VA reservation reference, ACPI integrity checker and Mach-O bundle/header validator. 19 tests passed in 0.106s; Python compilation and Info.plist parsing passed. Genuine macOS build/CI execution and hardware loading remain pending. Workflow YAML parser unavailable on the local Python environment; no parser validation claimed.

## 2026-10-12 — Research and baseline tooling

Reviewed Intel GuC/PRM documentation, versioned Linux Xe memory/submission/firmware documentation, Linux PCI source, Mesa ANV/release notes, Apple PCI/framebuffer documentation and translation/passthrough project prerequisites. Added staged implementation plan with claims, dependencies, acceptance criteria and source-fetch limitations.

Added Linux PCI metadata collector with four fixture tests. Combined suite: 8 tests passed in 0.158s. Python compileall passed with exit 0 and no diagnostics. No macOS C++/ASL builds or physical GPU tests performed.

Previous checkpoint 077cfe9 preserved supplied source and changed config preparation to require a new file with the experimental kext disabled. Original Downloads sources and USB remain untouched.
