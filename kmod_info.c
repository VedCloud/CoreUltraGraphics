/*
 * kmod_info.c -- kext module metadata.
 *
 * OpenCore's prelinked injection requires the _kmod_info symbol. It is not
 * emitted by ld64 (not even via -kext) and is not present in any Xcode SDK or
 * MacKernelSDK archive -- verified in CI runs 37789629143 and 37789952837,
 * where `nm --defined-only` over all six archives reported zero definitions.
 *
 * XNU provides it via extanTools/KernelModule.bproj/CreateKModInfo.perl, which
 * generates a C translation unit containing the KMOD_EXPLICIT_DECL macro and
 * compiles it to kmod_info.o. Both XNU's own libkern/kmod/README and
 * acidanthera/MacKernelSDK/Library/kmod/README specify the resulting link line:
 *
 *     *.o -lkmodc++ kmod_info.o -lkmod
 *
 * kmod_info.o must sit between -lkmodc++ and -lkmod, because C++ static
 * constructors leave .constructors_used undefined and libkmodc++ resolves it.
 *
 * The original perl script reads CustomInfo.xml through the legacy
 * /Developer/ProjectTypes xmldump, which no longer exists, so this file is the
 * fixed output of that script for this bundle. Keep the bundle identifier and
 * version in sync with Info.plist (CFBundleIdentifier / CFBundleVersion).
 *
 * Original CreateKModInfo.perl and osfmk/mach/kmod.h are Apple, Inc. code under
 * the Apple Public Source License Version 1.1. See THIRD-PARTY-LICENSES.md.
 */

#include <mach/mach_types.h>
#include <mach/kmod.h>

extern kern_return_t _start(kmod_info_t *ki, void *data);
extern kern_return_t _stop(kmod_info_t *ki, void *data);

KMOD_EXPLICIT_DECL("com.custom.CoreUltraGraphics", "0.3.0", _start, _stop)

__private_extern__ kmod_start_func_t *_realmain = 0;
__private_extern__ kmod_stop_func_t *_antimain = 0;
