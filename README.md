# CoreUltraGraphics investigation copy

Based on the user's downloaded source. The Downloads original remains untouched. This copy contains the reviewed source, a safer candidate-config utility, and Linux hardware metadata diagnostics. No native macOS acceleration is implemented.

Start with [the implementation plan](docs/IMPLEMENTATION_PLAN.md) and [source review](REVIEW.md).

Offline checks: `python -m unittest discover -v` and `python -m compileall -q inject_oc.py linux_baseline.py test_inject_oc.py test_linux_baseline.py`.

Linux metadata collection on the actual Latitude: `python3 linux_baseline.py`. No root, raw MMIO or PCI writes are requested. Read failures are reported explicitly. Actual firmware/engine state still needs separate evidence from the working Linux stack.

Configuration preparation: `python inject_oc.py COPIED_CONFIG --output NEW_CANDIDATE_PATH`. The result keeps the experimental kext disabled, preserves ACPI, and never overwrites existing files. Treat the candidate as private because it retains the original identifiers. No candidate or kext is installed automatically.

Do not enable current ring/display writes. Those experimental files are now excluded from the build. The driver is reduced to PCI identification without MMIO/decode changes or DMA. The Makefile discovers Xcode's SDK and accepts KERNEL_SDK for missing headers/libraries. The prepared GitHub workflow builds and inspects artifacts without loading them; it has not run yet.

Hardware is now measured as Latitude 5350, Intel 8086:7D45 revision 08. See [hardware evidence](docs/HARDWARE_BASELINE.md) and [current validation instructions](docs/TESTING.md). The original SSDT path differed from reported PC00; corrected source still requires namespace review before any use.
