/* SPDX-License-Identifier: MIT */
#ifndef NMX_BITCOUNT_COMPAT_H
#define NMX_BITCOUNT_COMPAT_H
#include <stddef.h>
/* Implemented by the port's nmx_misc.c; older kernel SDKs omit its prototype. */
void qsort(void *, size_t, size_t, int (*)(const void *, const void *));
/* LinuxKPI hweight macros use these FreeBSD libkern constant helpers. The
 * macOS libkern adapter omits them. Preserve truncation to the named width. */
#ifndef __const_bitcount8
#define __const_bitcount8(x) __builtin_popcount((unsigned char)(x))
#endif
#ifndef __const_bitcount16
#define __const_bitcount16(x) __builtin_popcount((unsigned short)(x))
#endif
#ifndef __const_bitcount32
#define __const_bitcount32(x) __builtin_popcount((unsigned int)(x))
#endif
#ifndef __const_bitcount64
#define __const_bitcount64(x) __builtin_popcountll((unsigned long long)(x))
#endif
#endif
