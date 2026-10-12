# Making CoreUltraGraphics work: research and implementation plan

Evidence reviewed 2026-10-12. Scope: the supplied C++/ASL/Python sources. No target hardware access, Apple SDK build or successful GPU execution is claimed.

## Decision

Keep the project, but replace the current execution experiment with a measured platform bring-up plan. First prove hardware execution through a narrow diagnostic interface. Investigate Apple graphics-provider integration in parallel as a separate feasibility gate. A working compute experiment does not prove a working Metal driver or accelerated desktop.

Do not prioritise AIR-to-SPIR-V translation now. The missing GPU address space, firmware and execution context would prevent even a correctly compiled shader from executing. Shader translation also does not supply Metal resource handling, pipeline state, synchronisation, or provider registration.

## What the research establishes

**Platform identification.** Mesa 24.1 release notes explicitly correct 7D45 to MTL-U. That supports the current match as a hypothesis; it does not measure the Latitude. Linux xe selects graphics/media IP using GMD_ID rather than assuming every subsystem from the PCI name. Do not extend current guessed register offsets to other devices. [Mesa](https://docs.mesa3d.org/relnotes/24.1.0.html), [Linux PCI implementation](https://github.com/torvalds/linux/blob/v6.12/drivers/gpu/drm/xe/xe_pci.c).

**Memory.** CPU allocation and GPU binding are different operations. Xe uses buffer objects, GPU VMs and explicit bindings, with synchronisation and rebinding when backing memory changes. The existing getPhysicalAddress result cannot be substituted for a validated GPU virtual address. Darwin needs a backend for page pinning/DMA addressing, GPU page-table construction, cache visibility and lifetime management. [Xe memory design](https://docs.kernel.org/6.12/gpu/xe/xe_mm.html).

**Firmware.** GuC communication, firmware layout and protected-memory setup are real bring-up dependencies. Meteor Lake HuC uses the GSC layout; this must not be treated as the older CSS image format. Separate essential render submission from later media/HuC and display/DMC functionality. Do not promise firmware authentication from successfully copying a blob. Exact files, versions, load sequence and terms remain to be verified against pinned platform code. [Firmware](https://docs.kernel.org/6.12/gpu/xe/xe_firmware.html), [Intel GuC API](https://www.intel.com/content/www/us/en/docs/graphics-for-linux/developer-reference/1-0/guc-kmd-api.html).

**Submission.** Xe separates VM binding from execution and uses explicit input/output fences and scheduler flow control. A ring-tail write in this project's dormant legacy experiment is not an implementation of that protocol. Reconstruct the minimal valid GuC context/queue lifecycle and error handling before emitting a batch. [Command submission](https://docs.kernel.org/6.12/gpu/xe/xe_cs.html).

**Userspace.** Mesa ANV is a Vulkan driver and depends on an appropriate kernel interface; its documentation also identifies GuC requirements on newer Intel platforms. It offers useful compiler/state-generation references, not a macOS kernel implementation. IGC is another compiler reference; do not assume every IGC path implements Vulkan or Metal semantics. Choose a compiler only after deciding the first workload and its language. [ANV](https://docs.mesa3d.org/drivers/anv.html), [IGC](https://github.com/intel/intel-graphics-compiler).

**Apple boundary.** PCIDriverKit exposes PCI-device support; IOFramebuffer describes a display-driver class. Neither referenced page establishes a public new-vendor Metal-provider registration mechanism. Determine the actual Intel macOS SDK/runtime interfaces, imports and user-client contracts before committing to a kernel/dext architecture. This is an unresolved research dependency, not proof that all paths are impossible. [PCI](https://developer.apple.com/documentation/pcidriverkit), [framebuffer](https://developer.apple.com/documentation/kernel/ioframebuffer), [Metal](https://developer.apple.com/documentation/metal).

**False shortcuts eliminated.** MoltenVK translates Vulkan through Metal, so it needs the Metal implementation we are missing. Passthrough documentation explicitly requires a macOS-supported iGPU; it does not supply a Meteor Lake driver. Matching an Ice Lake PCI ID cannot create Xe-LPG support. [MoltenVK](https://github.com/KhronosGroup/MoltenVK/blob/main/README.md), [passthrough prerequisites](https://github.com/LongQT-sea/intel-igpu-passthru/blob/main/macOS_README.md), [compatibility guide](https://github.com/dortania/GPU-Buyers-Guide/blob/master/modern-gpus/intel-gpu.md).

## Concrete work packages, in priority order

| Stage | Changes to this project | Evidence required to advance |
|---|---|---|
| A: baseline | Collect actual PCI/revision/driver, EFI/logs and original ACPI; stop assuming GFX0 | Real hardware inventory, known OpenCore/macOS versions, failure stage |
| B: build | Replace hardcoded SDK with explicit validated SDK selection; build diagnostic target separately from unused pipeline | Intel-capable macOS builder, compiler/SDK versions, full build output, symbols/imports and plist validation |
| C: passive probe | Verify PCI match; omit speculative display-register dump; avoid forced memory decode; use no GPU writes/DMA | SDK build and approved load; matching/unloading and failure cleanup observed |
| D: reference behavior | Run supported Linux graphics stack on the Latitude; record engine/IP topology and firmware success from private logs | Known kernel/Mesa/firmware versions; repeatable known-output workload |
| E: memory core | Define distinct CPU/DMA/GPU address types and bounds; backend interfaces for allocation, map/bind/unbind, coherency and fences | Portable tests for overlaps, lifetime, overflow and failed cleanup; actual GPU translation verified later |
| F: GuC bring-up | Implement validated power/reset, firmware state machine, protected-memory layout, communication and queues | Authenticated firmware/communication evidence, bounded timeouts, reset recovery |
| G: first execution | Submit minimal documented workload using an established VM/context; prefer a known-output store/copy experiment before a shader | GPU-written output, actual completion fence, repeated runs, negative tests and recovery |
| H: rendering | Reuse compiler/state references for one controlled render/compute workload with a narrow userspace client | Correct images/results, explicit execution and resource lifetime, no software fallback |
| I: display | Design proper platform modesetting and GGTT-backed scanout; remove CPU-address plane writes | Panel/link evidence, repeatable modes, vblank, backlight and suspend/resume |
| J: Apple integration | Determine provider and framework contracts; implement only after a defensible interface path exists | Real Metal device and workloads; separate WindowServer integration and stability |

Stages A and D require the physical laptop; B and C require macOS development access. E can proceed offline. Apple-interface research should run alongside D–H so success there does not mislead us about desktop feasibility. If provider integration stays blocked, preserve a useful diagnostic/compute result while investigating the limitation explicitly.

## Source investigation map

Use Linux v6.12 as an initial reproducible reference, not a claim it is the best kernel to install today. Pin actual commits and hashes before importing code. Map xe_uc_fw/xe_guc/xe_guc_ct/xe_guc_submit to firmware/queues; xe_bo/xe_vm/xe_ggtt/xe_pt to buffers and translation; xe_irq/xe_gt/xe_pm to interrupts, reset and power; shared Intel display code to panel bring-up. The listed files are the next line-by-line inspection queue; several direct source fetches failed, so their details are not yet audited.

Inspect Mesa ANV/Intel compiler and Xe winsys code with a fixed release; inspect IGT VM-bind, execution and reset tests as reference workloads. Keep GPL, MIT and other file-level obligations distinct and do not redistribute firmware without checking its terms.

Intel's reviewed PRM index describes hardware documentation but did not expose a Meteor Lake-specific entry in the fetched page. Alchemist/Tiger Lake documents are adjacent references, not permission to assume identical registers. Obtain the right platform revisions or corroborate every used field against measured IP and upstream implementation. [PRM index](https://www.intel.com/content/www/us/en/docs/graphics-for-linux/developer-reference/1-0/overview.html).

## First completed implementation in this cycle

Added linux_baseline.py: reads only PCI sysfs class/vendor/device/revision and the bound driver's symlink name. It avoids raw PCI config, BAR mappings, ROM access, serials and device path export. It flags whether actual metadata matches 8086:7D45 without claiming acceleration. Four fixture tests run on Windows validate filtering, mismatch, privacy and explicit failures. Physical Linux execution remains untested.

On an existing Linux installation/live session with Python 3, copy only the collector and run `python3 linux_baseline.py`. It installs nothing and changes no driver settings. No boot-media creation, driver rebinding or firmware modifications are authorised by this plan.

## Questions answered by the next evidence

Can the actual Latitude run a known-good Intel Linux workload? Does macOS fail before this kext is injected, during linking, during start, or after graphical transition? Is 7D45 the measured device? Which display/GT IP and firmware does the working stack identify? Can the diagnostic source build with a real selected SDK? What legitimate Apple provider interfaces are available on that chosen release?

Those answers determine implementation details. They should precede enabling any hardware-write path. No full-acceleration date or success claim is justified yet.
