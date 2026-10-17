"""Run the actual start/attach/stop methods with deterministic kernel doubles.

Exercise queued work, late completion, init failure and thread-create failure.
No hardware access. A delayed worker is deliberately held beyond the old timeout.
"""
from pathlib import Path
import subprocess, shutil, json, re
root=Path(__file__).resolve().parents[1]
source=(root/'port/nullmoth-candidate/nmx_kext.cpp').read_text()
out=root/'evidence/attach-lifecycle-tests'; out.mkdir(parents=True,exist_ok=True)
def method(signature):
    begin=re.search(re.escape(signature)+r'[^;\n]*\n\{',source).start()
    end=source.index('\n}\n',begin)+3
    return source[begin:end]
shim=r'''
#include <cassert>
#include <cstdio>
#include <cstdint>
#include <cstring>
using SInt32=int; using IOReturn=int; using IOOptionBits=unsigned;
using wait_result_t=int; using thread_t=void*; using kern_return_t=int;
struct kmod_info_t {};
#define THREAD_NULL nullptr
#define KERN_SUCCESS 0
#define KERN_FAILURE 5
#define kIOPCIConfigVendorID 0
#define kIOPCIConfigDeviceID 2
#define kIOPMPowerStateVersion1 1
#define kIOPMPowerOn 1
#define kOSBooleanTrue ((void*)1)
#define OSDynamicCast(type,p) dynamic_cast<type*>(p)
struct IOLock {};
static IOLock global_lock;
static bool g_started;
static int g_devices;
static IOLock *g_lock=&global_lock;
static int refs, thread_error, port_error, root_error, port_starts, port_stops, diagnostic_mode;
static int detach_calls, fb_unpublish, sleeps, run_at_sleep, claims;
static bool in_start, marker, firmware_ready;
static void (*queued)(void*,int); static void *queued_arg;
static int kernel_thread_start(void (*f)(void*,int),void *a,thread_t *t) {
    if(thread_error) return thread_error;
    queued=f; queued_arg=a; *t=(void*)1; return 0;
}
static void thread_deallocate(thread_t) {}
static void IOLockLock(IOLock*) {} static void IOLockUnlock(IOLock*) {}
static void IOLockFree(IOLock*) {}
static void run_worker() { auto f=queued; auto a=queued_arg; queued=nullptr; f(a,0); }
static void IOSleep(int) {
    ++sleeps;
    assert(detach_calls==0 && fb_unpublish==0);
    if(sleeps==run_at_sleep) run_worker();
    assert(sleeps<7000);
}
static int ml_get_interrupts_enabled() {return 1;}
static bool PE_parse_boot_argn(const char *name,int *v,unsigned) {
    if(!strcmp(name,"nmxdiag")) {*v=diagnostic_mode;return diagnostic_mode!=0;}
    *v=2;return true;
}
static int nmx_i915_set_guc_mode(int) {return 0;}
static int nmx_port_start() {assert(!in_start && firmware_ready);++port_starts;return port_error;}
static void nmx_port_stop() {++port_stops;}
static int nmx_port_busy() {return 0;}
static int nmx_xnu_wait_firmware_root(int) {firmware_ready=!root_error;return root_error;}
static bool nmx_marker_set() {return marker;}
static void nmx_marker_write(bool v) {marker=v;}
static void *nmx_port_attach(void*) {return (void*)2;}
static void nmx_port_detach(void*) {++detach_calls;}
static void OSSynchronizeIO() {}
struct IOPMPowerState {unsigned long a,b,c,d,e,f,g,h,i,j,k,l;};
class IOService {
public:
 virtual ~IOService()=default;
 virtual bool start(IOService*) {return true;}
 virtual void stop(IOService*) {}
 void retain() {++refs;} void release() {--refs;}
 void setProperty(const char*,const char*) {}
 void setProperty(const char*,void*) {++claims;}
 void removeProperty(const char*) {if(claims) --claims;}
 void registerService() {} void PMinit() {} void PMstop() {}
 void registerPowerDriver(IOService*,IOPMPowerState*,int) {}
};
class IOPCIDevice:public IOService {
public: unsigned configRead16(int n) {return n?0x7d45:0x8086;}
 void joinPMtree(IOService*) {}
};
static IOService fb;
static IOService *nmx_fb_publish(IOService*,void*) {return &fb;}
static void nmx_fb_unpublish(IOService*,IOService*,void*) {++fb_unpublish;}
class NMXGPU:public IOService {
public:
 void *dev_; IOService *fb_; IOPCIDevice *pci_; volatile int attach_; bool pm_;
 unsigned attach_thread_stage_,attach_thread_done_,attach_cancel_;
 bool start(IOService*) override; void stop(IOService*) override;
 static void attachThread(void*,int); void attachNow();
};
'''
body='\n'.join(method(s) for s in ['bool NMXGPU::start(', 'void NMXGPU::attachThread(',
    'void NMXGPU::attachNow(', 'void NMXGPU::stop(', 'kern_return_t nmx_kmod_stop('])
cases=r'''
static void reset() {
 refs=thread_error=port_error=root_error=port_starts=port_stops=diagnostic_mode=0;
 detach_calls=fb_unpublish=sleeps=run_at_sleep=claims=g_devices=0;
 in_start=marker=firmware_ready=g_started=false;
 queued=nullptr;g_lock=&global_lock;
}
static bool start(NMXGPU &gpu, IOPCIDevice &pci) {
 in_start=true;bool r=gpu.start(&pci);in_start=false;return r;
}
int main() {
 IOPCIDevice pci;
 { reset();NMXGPU gpu{};
   assert(start(gpu,pci)); assert(port_starts==0 && refs==1 && g_devices==1);
   assert(nmx_kmod_stop(nullptr,nullptr)==KERN_FAILURE); // even before g_started
   run_worker(); assert(port_starts==1 && refs==0 && g_started && claims==1);
   gpu.stop(&pci);assert(g_devices==0 && fb_unpublish==1 && !claims);
   assert(nmx_kmod_stop(nullptr,nullptr)==0 && port_stops==1);
 }
 { reset();NMXGPU gpu{};thread_error=5;
   assert(!start(gpu,pci));assert(!queued && refs==0 && !g_devices && !port_starts);
   assert(nmx_kmod_stop(nullptr,nullptr)==0);
 }
 { reset();NMXGPU gpu{};port_error=12;
   assert(start(gpu,pci));run_worker();assert(!g_started && !marker && !claims);
   assert(nmx_kmod_stop(nullptr,nullptr)==KERN_FAILURE);
   gpu.stop(&pci);assert(!g_devices && !fb_unpublish);
 }
 { reset();NMXGPU gpu{};root_error=60;
   assert(start(gpu,pci));run_worker();assert(!port_starts && !marker);
   gpu.stop(&pci);assert(!g_devices);
 }
 { reset();NMXGPU gpu{};
   assert(start(gpu,pci));run_at_sleep=6002;
   gpu.stop(&pci); // old code detached after 6000 without joining
   assert(sleeps==6002 && !queued && refs==0 && !port_starts && !g_devices);
 }
 { reset();NMXGPU gpu{};diagnostic_mode=1;
   assert(start(gpu,pci));run_worker();
   assert(gpu.attach_thread_stage_==5 && gpu.attach_thread_done_==1);
   assert(!port_starts && !claims && !marker && !firmware_ready && !g_started && refs==0);
   gpu.stop(&pci);assert(!g_devices && !fb_unpublish);
 }
 puts("PASS: 6 production lifecycle scenarios, including late worker join and hardware-free diagnostic");
}
'''
file=out/'lifecycle.cpp';file.write_text(shim+body+cases,newline='\n')
compiler=shutil.which('clang++') or shutil.which('g++')
if compiler:
    command=[compiler,'-std=c++17',str(file),'-o',str(out/'lifecycle')]
else:
    zig=Path(r'C:/Users/Ved/Desktop/macOS Project/intel-macos/tooling/re-tools/ziglang/zig.exe')
    command=[str(zig),'c++','-std=c++17',str(file),'-o',str(out/'lifecycle.exe')]
subprocess.run(command,check=True)
run=subprocess.run([str(out/('lifecycle.exe' if not compiler else 'lifecycle'))],capture_output=True,text=True,timeout=15)
(out/'result.json').write_text(json.dumps(dict(exit_code=run.returncode,stdout=run.stdout,stderr=run.stderr),indent=2)+'\n')
print(run.stdout);print(run.stderr);run.check_returncode()
