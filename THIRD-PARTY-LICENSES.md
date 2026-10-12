# Third-party licences

## XNU kext module metadata (`kmod_info`)

`kmod_info.c` in this repository is derived from Apple, Inc. XNU sources:

- `osfmk/mach/kmod.h` — supplies `KMOD_EXPLICIT_DECL`, `kmod_info_t`
  (https://github.com/apple-oss-distributions/xnu)
- `EXTRATOOLS/KernelModule.bproj/CreateKModInfo.perl` — the generator whose
  fixed output `kmod_info.c` reproduces
  (https://github.com/minombreesjeff/darwin_env/blob/master/Tools/extenTools/KernelModule.bproj/CreateKModInfo.perl)

Both are licensed under the Apple Public Source License Version 1.1:

```
@APPLE_LICENSE_HEADER_START@

The contents of this file constitute Original Code as defined in and
are subject to the Apple Public Source License Version 1.1 (the
"License").  You may not use this file except in compliance with the
License.  You may obtain a copy of the License at
http://www.apple.com/publicsource and read it before using this file.

This Original Code and all software distributed under the License is
provided on an "AS IS" basis and APPLE HEREBY DISCLAIMS ALL WARRANTIES,
EXPRESS OR IMPLIED, INCLUDING WITHOUT LIMITATION, ANY WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NON-INFRINGEMENT.
APPLE HEREBY IS NOT LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT
OF OR IN CONNECTION WITH THE APPLE SOFTWARE OR THE USE OR OTHER DEALINGS
IN THE APPLE SOFTWARE.

@APPLE_LICENSE_HEADER_END@
```

The link-line requirement documented in `kmod_info.c`
(`*.o -lkmodc++ kmod_info.o -lkmod`) is taken from XNU's own
`libkern/kmod/README`, and is reproduced here for reference.

## MacKernelSDK — pinned CI build dependency

The prepared workflow now retrieves revision `3f750085caa17ec3a7880f11c11bf4f48cd6a164` for kernel headers and x86_64 libraries. It is not vendored in this source package. Review its [upstream licence](https://github.com/acidanthera/MacKernelSDK/blob/3f750085caa17ec3a7880f11c11bf4f48cd6a164/LICENSE.txt) and individual files before redistribution. SDK compilation does not establish runtime compatibility.

The following earlier investigation notes are inherited source claims, not independently reproduced in this Windows session:

CI run `37789952837` tested `acidanthera/MacKernelSDK` at pinned revision
`3f750085caa17ec3a7880f11c11bf4f48cd6a164`. Its `Library/x86_64/libkmod.a`
contains exactly the same members Xcode's SDK ships (`__.SYMDEF SORTED`,
`c_start.o`, `c_stop.o`), and `nm --defined-only` reported **zero**
definitions of `_kmod_info` across all of its archives. It is therefore
**not** a dependency of this project and is not vendored or downloaded.

To reproduce that check:

```
curl -sSL https://codeload.github.com/acidanthera/MacKernelSDK/tar.gz/3f750085caa17ec3a7880f11c11bf4f48cd6a164 \
  | tar -xz -C /tmp/mks --strip-components=1
nm --defined-only /tmp/mks/Library/x86_64/libkmod.a | grep -c _kmod_info   # -> 0
```

MacKernelSDK itself carries no SPDX licence identifier upstream
(`license: NOASSERTION`); its contents are derived from the same
APL-1.1 XNU material above.
