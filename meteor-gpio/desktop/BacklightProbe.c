#include <IOKit/IOKitLib.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>
static volatile sig_atomic_t interrupted=0;
static void stop_test(int unused){(void)unused;interrupted=1;}
int main(int argc,char **argv) {
    if(argc<2 || argc>3 || (strcmp(argv[1],"status") && strcmp(argv[1],"test"))) {
        fprintf(stderr,"Usage: sudo BacklightProbe status | sudo BacklightProbe test 70\nTest temporarily sets a firmware-supported level for5seconds, then restores it.\n");return 2;
    }
    io_service_t service=IOServiceGetMatchingService(kIOMainPortDefault,IOServiceMatching("LatitudeBacklightProbe"));
    if(!service){fprintf(stderr,"Diagnostic backlight bridge not loaded.\n");return 3;}
    io_connect_t connection=IO_OBJECT_NULL;
    kern_return_t result=IOServiceOpen(service,mach_task_self(),0,&connection);
    IOObjectRelease(service);
    if(result){fprintf(stderr,"Open failed0x%x (run with sudo).\n",result);return 4;}
    uint64_t status[6]={0};uint32_t count=6;
    result=IOConnectCallScalarMethod(connection,0,NULL,0,status,&count);
    printf("status=0x%x BCM=0x%llx BQC=0x%llx current=%llu min=%llu max=%llu supported-level-count=%llu\n",
           result,status[0],status[1],status[2],status[3],status[4],status[5]);
    if(!result && !strcmp(argv[1],"test")) {
        char *end=NULL;long parsed=argc==3?strtol(argv[2],&end,10):70;
        if((argc==3 && (!end || *end)) || parsed<5 || parsed>100)result=kIOReturnBadArgument;
        else {
            uint64_t level=(uint64_t)parsed;
            signal(SIGINT,stop_test);signal(SIGTERM,stop_test);signal(SIGHUP,stop_test);
            result=IOConnectCallScalarMethod(connection,1,&level,1,NULL,NULL);
            printf("set-test=0x%x; observe PHYSICAL screen brightness, not just reported value.\n",result);
            if(!result)for(int i=0;i<50&&!interrupted;i++)usleep(100000);
        }
    }
    // clientClose restores the first valid original level even if interrupted.
    IOServiceClose(connection);
    printf("Connection closed; restoration requested if the test changed a level.\n");
    return result?5:0;
}
