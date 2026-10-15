"""Execute the actual read-only platform query against simulated pad registers."""
from pathlib import Path
import subprocess,tempfile
s=(Path(__file__).resolve().parent/'readiness/VoodooGPIOIntel.cpp').read_text()
start=s.index('IOReturn VoodooGPIOIntel::callPlatformFunction(')
end=s.index('\n#define PADCFG1',start)
method=s[start:end]
assert 'writel(' not in method and 'setInterrupt' not in method
program=r'''
#include <cassert>
#include <cstring>
#include <cstdint>
using UInt32=uint32_t; using SInt32=int32_t; using IOVirtualAddress=uintptr_t; using IOReturn=int;
constexpr int kIOReturnSuccess=0,kIOReturnUnsupported=1,kIOReturnNotReady=2,kIOReturnNotFound=3,kIOReturnBadArgument=4;
constexpr unsigned PADCFG0=0,PADCFG0_PMODE_MASK=0x3c00,PADCFG0_GPIORXDIS=512,PADCFG0_GPIOTXDIS=256;
struct OSSymbol {const char* s; bool isEqualTo(const char* t) const{return !strcmp(s,t);} };
struct intel_community {uintptr_t regs=1;}; struct intel_padgroup {};
static unsigned value=258,reads=0;
unsigned readl(uintptr_t){++reads;return value;}
struct Base {int callPlatformFunction(const OSSymbol*,bool,void*,void*,void*,void*){return 99;}};
using VoodooGPIO=Base;
struct Meta {const char* name="VoodooGPIOMeteorLakeP"; const char* getClassName(){return name;}};
struct VoodooGPIOIntel:Base {
 bool controllerIsAwake=true,inactive=false,missing=false;int pin=232;Meta meta;intel_community comm;intel_padgroup group;
 bool isInactive(){return inactive;} Meta* getMetaClass(){return &meta;}
 SInt32 intel_gpio_to_pin(unsigned offset,intel_community** c,intel_padgroup** g){assert(offset==387);*c=&comm;*g=&group;return pin;}
 uintptr_t intel_get_padcfg(unsigned p,unsigned r){assert(p==232&&r==0);return missing?0:1;}
 int callPlatformFunction(const OSSymbol*,bool,void*,void*,void*,void*);
};
METHOD
int main(){
 VoodooGPIOIntel g;OSSymbol name{"LatitudeELANReadPad232"},other{"other"};unsigned p=0;
 auto run=[&](){return g.callPlatformFunction(&name,false,&p,nullptr,nullptr,nullptr);};
 assert(run()==0&&p==258); // high: input valid, do not read I2C
 value=256;assert(run()==0&&p==256); // low: data ready
 value=768;assert(run()==kIOReturnUnsupported); // receiver disabled
 value=1280;assert(run()==kIOReturnUnsupported); // wrong pin mux
 value=0;assert(run()==kIOReturnUnsupported); // output enabled
 unsigned before=reads;g.controllerIsAwake=false;assert(run()==kIOReturnNotReady&&reads==before);
 g.controllerIsAwake=true;g.inactive=true;assert(run()==kIOReturnNotReady&&reads==before);
 g.inactive=false;g.pin=231;assert(run()==kIOReturnNotFound&&reads==before);
 g.pin=232;g.missing=true;assert(run()==kIOReturnNotFound&&reads==before);
 g.missing=false;g.meta.name="OtherGPIO";assert(run()==kIOReturnBadArgument&&reads==before);
 assert(g.callPlatformFunction(&other,false,&p,nullptr,nullptr,nullptr)==99);
 g.meta.name="VoodooGPIOMeteorLakeP";assert(g.callPlatformFunction(&name,false,nullptr,nullptr,nullptr,nullptr)==kIOReturnBadArgument);
}
'''.replace('METHOD',method)
with tempfile.TemporaryDirectory() as d:
    d=Path(d);(d/'test.cpp').write_text(program)
    subprocess.run(['clang++','-std=c++17',str(d/'test.cpp'),'-o',str(d/'test')],check=True)
    subprocess.run([str(d/'test')],check=True)
print('Read-only GPIO query: high/low, mux, RX/output disable, sleep, inactive, mapping, wrong device and null checks passed; no writes.')
