"""Compile/run production bridge control flow with fault-injected kernel API doubles."""
from pathlib import Path
import json
import subprocess
import shutil

root = Path(__file__).resolve().parents[1]
source = root/'port/nullmoth-candidate/nmx_i915_bridge.c'
out = root/'evidence/intel-bridge-build'
out.mkdir(parents=True, exist_ok=True)
shim = r'''
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <stdbool.h>
#include <assert.h>
#include "nmx_i915_bridge.h"
#include "nmx_scanout_range.h"
#include "nmx_bitcount_compat.h"
#define EINVAL 22
#define ENODEV 19
#define ENOMEM 12
#define ENXIO 6
#define ERANGE 34
#define EIO 5
#define EDEADLK 11
#define ENABLE_GUC_MASK 3
#define GFP_KERNEL 0
#define DRM_FORMAT_MOD_LINEAR 0
#define PIN_MAPPABLE 4
#define __iomem
#define ERR_PTR(n) ((void *)(intptr_t)(n))
#define IS_ERR(p) ((uintptr_t)(p) >= (uintptr_t)-4095)
#define PTR_ERR(p) ((int)(intptr_t)(p))
typedef unsigned long intel_wakeref_t;
struct drm_driver { const char *name; };
struct drm_device { struct drm_driver *driver; };
struct drm_client_dev { struct drm_device *dev; };
struct drm_gem_object { uint64_t size; };
struct drm_i915_gem_object { struct drm_gem_object base; };
struct drm_framebuffer { uint64_t modifier; };
struct drm_client_buffer { struct drm_client_dev *client; struct drm_gem_object *gem; struct drm_framebuffer *fb; };
struct resource { uint64_t start, size; };
struct i915_ggtt { struct resource gmadr; uint64_t mappable_end; };
struct i915_vma { struct i915_ggtt *vm; uint64_t offset, size; };
struct drm_i915_private { struct drm_device drm; int runtime_pm; bool lmem, wedged; };
struct i915_gem_ww_ctx { int live; };
struct iosys_map { void *vaddr_iomem; bool is_iomem; };
static struct { int enable_guc; } i915_modparams;
static struct { int allocations, power, locks, pins, iomaps, references, fault, lock_attempt; } state;
static struct i915_vma global_vma;
#define to_i915(p) ((struct drm_i915_private *)(p))
#define to_intel_bo(p) ((struct drm_i915_gem_object *)(p))
#define to_gt(p) (p)
#define intel_gt_is_wedged(p) ((p)->wedged)
#define HAS_LMEM(p) ((p)->lmem)
#define resource_size(p) ((p)->size)
#define i915_vm_to_ggtt(p) (p)
#define i915_ggtt_offset(p) ((p)->offset)
#define i915_vma_size(p) ((p)->size)
static void *kzalloc(size_t n,int flags) { (void)flags; if(state.fault==1)return NULL; ++state.allocations; return calloc(1,n); }
static void kfree(void *p) { assert(p); --state.allocations; free(p); }
static unsigned long intel_runtime_pm_get(int *p) { (void)p; ++state.power; return 1; }
static void intel_runtime_pm_put(int *p,unsigned long ref) { (void)p; assert(ref==1); --state.power; }
static void i915_gem_ww_ctx_init(struct i915_gem_ww_ctx *w,bool intr) { (void)intr;w->live=1; ++state.locks; }
static void i915_gem_ww_ctx_fini(struct i915_gem_ww_ctx *w) { assert(w->live);w->live=0;--state.locks; }
static int i915_gem_object_lock(struct drm_i915_gem_object *o,struct i915_gem_ww_ctx *w) {
    (void)o;assert(w->live); ++state.lock_attempt;
    if(state.fault==2)return -EIO;
    if((state.fault==7 || state.fault==8) && state.lock_attempt==1)return -EDEADLK;
    return 0;
}
static int i915_gem_ww_ctx_backoff(struct i915_gem_ww_ctx *w) { assert(w->live);return state.fault==8?-EIO:0; }
static struct i915_vma *i915_gem_object_ggtt_pin_ww(struct drm_i915_gem_object *o,struct i915_gem_ww_ctx *w,
    void *view,uint64_t size,uint64_t alignment,uint64_t flags) {
    (void)o;(void)view;(void)size;(void)alignment;assert(w->live);assert(flags&PIN_MAPPABLE);
    if(state.fault==3)return ERR_PTR(-ENOMEM); ++state.pins;return &global_vma;
}
static bool i915_vma_is_map_and_fenceable(struct i915_vma *v) { (void)v;return state.fault!=4; }
static void *i915_vma_pin_iomap(struct i915_vma *v) { (void)v;if(state.fault==6)return ERR_PTR(-ENOMEM);++state.iomaps;return (void *)0x100000; }
static void i915_vma_unpin_iomap(struct i915_vma *v) { (void)v;--state.iomaps; }
static void i915_vma_unpin(struct i915_vma *v) { (void)v;--state.pins; }
static struct i915_vma *i915_vma_get(struct i915_vma *v) { ++state.references; return v; }
static void i915_vma_put(struct i915_vma *v) { (void)v;--state.references; }
static void iosys_map_clear(struct iosys_map *m) { memset(m,0,sizeof(*m)); }
static void iosys_map_set_vaddr_iomem(struct iosys_map *m,void *p) { m->vaddr_iomem=p;m->is_iomem=true; }
'''
main = r'''
static void balanced(void) {
    assert(state.allocations==0 && state.power==0 && state.locks==0);
    assert(state.pins==0 && state.iomaps==0 && state.references==0);
}
int main(void) {
    for(unsigned value=0;value<65536;++value) {
        unsigned bits=0;
        for(unsigned v=value;v;v>>=1)bits+=v&1;
        assert((unsigned)__const_bitcount16(value)==bits);
        assert(__const_bitcount8(value)==__const_bitcount16(value&255));
    }
    assert(__const_bitcount32(UINT64_MAX)==32);
    assert(__const_bitcount64(UINT64_MAX)==64);
    struct drm_driver driver={"i915"};
    struct drm_i915_private i915={{&driver},0,false,false};
    struct drm_client_dev client={&i915.drm};
    struct drm_i915_gem_object obj={{8192}};
    struct drm_framebuffer fb={0};
    struct drm_client_buffer buffer={&client,&obj.base,&fb};
    struct i915_ggtt ggtt={{0x80000000,0x1000000},0x1000000};
    unsigned cases=0;
    for(int fault=0;fault<=8;++fault) {
        memset(&state,0,sizeof(state));state.fault=fault;
        global_vma=(struct i915_vma){&ggtt,fault==5?0x1000000:4096,8192};
        uint64_t physical=0xbad;struct nmx_i915_mapping *mapping=(void*)0xbad;struct iosys_map map={0};
        int err=nmx_i915_fb_map(&buffer,&map,8192,&physical,&mapping);
        if(fault==0 || fault==7) {
            assert(err==0 && mapping && physical==0x80001000 && map.is_iomem);
            assert(state.allocations==1 && state.power==1 && state.pins==1 && state.iomaps==1 && state.references==1);
            if(fault==7)assert(state.lock_attempt==2);
            nmx_i915_fb_unmap(mapping);
        } else assert(err<0 && !physical && !mapping && !map.vaddr_iomem);
        balanced();++cases;
    }
    memset(&state,0,sizeof(state));
    for(int mode=-1;mode<=4;++mode) {
        i915_modparams.enable_guc=99;
        int err=nmx_i915_set_guc_mode(mode);
        assert(err==((mode<0 || mode>3)?-EINVAL:0));
        assert(i915_modparams.enable_guc==((mode<0 || mode>3)?99:mode));++cases;
    }
    for(int invalid=0;invalid<5;++invalid) {
        driver.name=invalid==0?"amdgpu":"i915";
        i915.wedged=invalid==1;i915.lmem=invalid==2;fb.modifier=invalid==3?1:0;
        uint64_t physical=0xbad;struct nmx_i915_mapping *mapping=(void*)0xbad;struct iosys_map map={0};
        int err=nmx_i915_fb_map(invalid==4?NULL:&buffer,&map,8192,&physical,&mapping);
        assert(err<0 && !physical && !mapping);balanced();++cases;
    }
    uint64_t p;
    assert(!nmx_scanout_range(UINT64_MAX-4095,8192,8192,4096,4096,4096,4096,&p) && !p);++cases;
    assert(!nmx_scanout_range(0x80000000,8192,4096,4096,4096,4096,4096,&p) && !p);++cases;
    assert(!nmx_scanout_range(0x80000000,8192,8192,0,4096,4096,8192,&p) && !p);++cases;
    assert(nmx_scanout_range(0x80000000,8192,8192,4096,4096,4096,4096,&p) && p==0x80001000);++cases;
    printf("PASS: %u lifecycle, fault, GuC-policy and aperture-range cases; 65536 bitcount inputs; kernel calls simulated.\n",cases);
    return 0;
}
'''
actual = '\n'.join(line for line in source.read_text().splitlines() if not line.startswith('#include'))
fixture = out/'test-bridge.c'
fixture.write_text(shim+actual+main, newline='\n')
exe = out/'test-bridge.exe'
command = [str(root/'tooling/re-tools/ziglang/zig.exe'), 'cc', '-std=c11', '-Wall', '-Wextra', '-Werror',
           '-I', str(source.parent), str(fixture), '-o', str(exe)]
if not Path(command[0]).exists():
    compiler = shutil.which('clang') or shutil.which('cc')
    if not compiler:
        raise RuntimeError('Install clang or set up the bundled Zig compiler before running the host tests.')
    command = [compiler] + command[2:]
build = subprocess.run(command,capture_output=True,text=True,check=True)
run = subprocess.run([str(exe)],capture_output=True,text=True,check=True)
result = dict(result=run.stdout.strip(), compiler_stderr=build.stderr,
              limitations='Production C control flow with kernel API doubles, not hardware/macos runtime validation.')
(out/'test-results.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
