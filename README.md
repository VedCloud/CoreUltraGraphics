# CoreUltraGraphics

Experimental Intel Meteor Lake 8086:7D45 macOS driver research and diagnostic
kext. **GPU acceleration, Metal and WindowServer acceleration are not implemented.**

The graphics workflow builds a read-only GPU identification probe with a pinned
MacKernelSDK. It tests the portable command encoders,
firmware containers and GuC setup-message decoder. Peripheral workflows remain
separate. See [build and test instructions](docs/BUILD_AND_TEST.md).

Probe version 0.3.0 reports PCI identity and resource metadata, then attempts two
read-only GMD_ID register reads through BAR0. It checks memory decoding, PCI D0,
BAR type, resource identity and access bounds, and releases the mapping immediately.
It does not change PCI configuration, write GPU registers, request forcewake,
allocate DMA, initialize GuC, submit render work or install itself into an EFI.
See [the register access scope and source references](docs/MMIO_PROBE.md).
The excluded experimental translation pipeline has unimplemented shader translation and
uses CPU physical addresses in dormant ring/display code. A successful compile
does not make those paths suitable for use on Meteor Lake hardware.
