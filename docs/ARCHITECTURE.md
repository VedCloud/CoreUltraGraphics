# Implemented and proposed boundaries

Implemented offline: config-candidate preparation, Linux PCI metadata collector, GPU VA reservation reference core, ACPI integrity checks and Mach-O artifact inspection.

Implemented source, awaiting macOS compilation: CoreUltraGraphicsDriver IOService identification probe; only reads vendor/device/revision, retains/releases provider and registers the service. No MMIO mapping, decode changes, scratch DMA or speculative display reads.

Unimplemented backend: page pinning/DMA translation, GPU GGTT/PPGTT binding, firmware/authentication/GuC communication, contexts/queues, synchronisation/interrupts/reset/power, modesetting and Apple rendering integration. The Python reservation object is not a hardware mapping and must never be treated as one.

The unfinished XeTranslationPipeline is excluded from the production object list. IOFramebuffer/Metal research remains a separate milestone from raw execution. See IMPLEMENTATION_PLAN.md for the complete dependency chain.
