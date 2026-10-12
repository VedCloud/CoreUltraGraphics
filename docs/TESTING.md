# Validation and build procedure

Windows offline checks: `python -m unittest discover -v` and `python -m compileall -q .`.

GPU VA reservation tests cover aligned nonoverlapping allocation, holes/exhaustion, stale/foreign handle rejection, bounds and 1500 deterministic random operations. This Python component reserves addresses only; it does not bind memory, programme page tables or submit commands. Caller must serialise access.

ACPI table checks validate byte length/checksum without evaluating AML. Mach-O checks validate expected thin x86_64 kext file type and load-command boundaries; they cannot validate imports, ABI compatibility or hardware behavior. Fixture headers are synthetic, not compiled artifacts.

Prepared GitHub Actions workflow: copy this project source to the repository root, including .github/workflows/build.yml. Run Actions → Diagnostic probe build → Run workflow. It retrieves a pinned MacKernelSDK revision, records environment/revisions, runs offline tests, compiles the identification-only kext, validates plist/header/defined kmod_info, records imports and saves complete logs. If compilation fails, the build log is uploaded for the next repair cycle. No kext is loaded or installed.

Mac build manually: `make KERNEL_SDK=/absolute/path/to/MacKernelSDK`. SDK is resolved through xcrun or an explicit SDK=... value. Header paths are checked before compilation. The pinned SDK is a community kernel SDK with mixed version headers/libraries; runtime compatibility still needs selected-OS validation. [SDK instructions](https://github.com/acidanthera/MacKernelSDK), [runner image](https://github.com/actions/runner-images/blob/main/images/macos/macos-15-Readme.md).

Current local host lacks Apple tools/SDK and a C++ compiler. Visual Studio installation has no discovered VC compiler toolset. No genuine kext compile, ASL compile or CI run performed yet. Workflow preparation is not a successful build.

Before any target load: inspect successful build output/imports, match actual macOS build and OpenCore release, preserve EFI backup and obtain the user's approval for experimental loading. Even an identification-only IOService attachment can affect provider matching; zero IOProbeScore does not prove harmless coexistence.
