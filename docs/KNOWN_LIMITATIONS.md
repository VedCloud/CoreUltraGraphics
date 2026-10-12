# Current limitations

- Native macOS acceleration not implemented. No Metal/framebuffer provider, firmware loader, GPU binding, scheduler or recovery backend.
- Probe reduced to PCI identification; macOS compilation/loading untested. Attaching to the GPU can still influence provider matching.
- Legacy translation/ring/display files retained as historical experimental source but excluded from the kext build; their hardware-write APIs remain unsuitable for deployment.
- Corrected SSDT namespace still needs ACPI decompilation, _DSM collision checks and actual EFI rename review. No injection or compiled AML.
- Offline GPU VA reservation core is a Python reference component with no hardware page-table backend.
- Linux report establishes initialisation/display and firmware observations, not completed render workloads, performance or macOS compatibility.
- Actual EFI and macOS/OpenCore failure trace still missing. Driver build workflow prepared but not run or pushed.
