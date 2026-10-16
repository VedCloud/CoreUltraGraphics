# CoreUltraGraphics

Experimental Intel Meteor Lake 8086:7D45 macOS driver research and diagnostic
kext. **GPU acceleration, Metal and WindowServer acceleration are not implemented.**

The graphics workflow builds the existing diagnostic driver and dormant translation
pipeline with a pinned MacKernelSDK. It tests the portable command encoders,
firmware containers and GuC setup-message decoder. Peripheral workflows remain
separate. See [build and test instructions](docs/BUILD_AND_TEST.md).

The diagnostic driver enables PCI memory decode and reads display registers;
it does not initialize GuC, submit render work or install itself into an EFI.
The experimental translation pipeline has unimplemented shader translation and
uses CPU physical addresses in dormant ring/display code. A successful compile
does not make those paths suitable for use on Meteor Lake hardware.
