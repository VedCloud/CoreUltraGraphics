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

## MacKernelSDK — pinned kernel headers

CI run `37789952837` tested `acidanthera/MacKernelSDK` at pinned revision
`3f750085caa17ec3a7880f11c11bf4f48cd6a164`. Its `Library/x86_64/libkmod.a`
contains exactly the same members Xcode's SDK ships (`__.SYMDEF SORTED`,
`c_start.o`, `c_stop.o`), and `nm --defined-only` reported **zero**
definitions of `_kmod_info` across all of its archives. That result concerns
module metadata, not whether its headers are useful. The graphics diagnostic
workflow and Intel source rebuild now use its pinned kernel headers. The build
fetcher downloads the source archive; it is not vendored in this repository.

To reproduce that check:

```
curl -sSL https://codeload.github.com/acidanthera/MacKernelSDK/tar.gz/3f750085caa17ec3a7880f11c11bf4f48cd6a164 \
  | tar -xz -C /tmp/mks --strip-components=1
nm --defined-only /tmp/mks/Library/x86_64/libkmod.a | grep -c _kmod_info   # -> 0
```

MacKernelSDK itself carries no SPDX licence identifier upstream
(`license: NOASSERTION`); its contents are derived from the same
APL-1.1 XNU material above.

## Experimental Intel port overlay

`research/intel-port` contains standalone MIT-noticed helpers and modifications
to the NullMoth port at `277a29bea10371a88c4c1fb104409060d31962e8`. The upstream
port and derived overlay remain subject to PolyForm Noncommercial 1.0.0; the
full terms are included at `research/intel-port/LICENSE.NULLMOTH.txt`.

The dependency fetcher preserves pinned Intel/DRM/FreeBSD/Apple input notices.
These dependencies retain their upstream licences. The source archive's NPU
licence notices also remain with its extracted contents. New helper SPDX
notices do not relicense the combined driver. This source overlay does not
redistribute firmware or the upstream Metal plug-in.
