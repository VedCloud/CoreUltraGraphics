// Executes a compute workload only on the Metal device backed by 8086:7D45.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#import <IOKit/IOKitLib.h>
#include <dlfcn.h>
#include <stdint.h>
#include <string.h>
#include <dispatch/dispatch.h>

static BOOL targetDevice(id<MTLDevice> device)
{
    io_registry_entry_t entry = IOServiceGetMatchingService(kIOMainPortDefault,
                                     IORegistryEntryIDMatching(device.registryID));
    for (unsigned depth = 0; entry && depth < 8; ++depth) {
        CFTypeRef vendor = IORegistryEntryCreateCFProperty(entry, CFSTR("vendor-id"), kCFAllocatorDefault, 0);
        CFTypeRef product = IORegistryEntryCreateCFProperty(entry, CFSTR("device-id"), kCFAllocatorDefault, 0);
        BOOL found = NO;
        if (vendor && product && CFGetTypeID(vendor) == CFDataGetTypeID() &&
            CFGetTypeID(product) == CFDataGetTypeID() &&
            CFDataGetLength((CFDataRef)vendor) >= 2 && CFDataGetLength((CFDataRef)product) >= 2) {
            const UInt8 *v = CFDataGetBytePtr((CFDataRef)vendor);
            const UInt8 *p = CFDataGetBytePtr((CFDataRef)product);
            found = (v[0] == 0x86 && v[1] == 0x80 && p[0] == 0x45 && p[1] == 0x7d);
        }
        if (vendor) CFRelease(vendor);
        if (product) CFRelease(product);
        if (found) { IOObjectRelease(entry); return YES; }
        io_registry_entry_t parent = 0;
        IOReturn result = IORegistryEntryGetParentEntry(entry, kIOServicePlane, &parent);
        IOObjectRelease(entry);
        entry = result == KERN_SUCCESS ? parent : 0;
    }
    if (entry) IOObjectRelease(entry);
    return NO;
}

int main(int argc, const char *argv[])
{
    @autoreleasepool {
        if (argc == 2 && strcmp(argv[1], "--check-csr") == 0) {
            typedef int (*csr_get_t)(uint32_t *);
            csr_get_t getter = (csr_get_t)dlsym(RTLD_DEFAULT, "csr_get_active_config");
            uint32_t active = 0;
            if (!getter || getter(&active) != 0) {
                fprintf(stderr, "Cannot inspect the running kernel's CSR configuration. No installation performed.\n");
                return 2;
            }
            printf("Running CSR configuration: 0x%08x\n", active);
            return (active & 0x0a43u) == 0x0a43u ? 0 : 2;
        }
        NSArray<id<MTLDevice>> *devices = MTLCopyAllDevices();
        id<MTLDevice> device = nil;
        for (id<MTLDevice> candidate in devices) {
            printf("Metal candidate: %s; registryID=0x%llx\n", candidate.name.UTF8String,
                   (unsigned long long)candidate.registryID);
            if (targetDevice(candidate)) device = candidate;
        }
        if (!device) { fprintf(stderr, "FAIL: no Metal device backed by Intel 8086:7D45.\n"); return 3; }
        NSError *error = nil;
        NSString *source = @"#include <metal_stdlib>\nusing namespace metal;\n"
                           "kernel void cug_fill(device uint *out [[buffer(0)]], uint i [[thread_position_in_grid]]) {"
                           " out[i] = (i * 17u) ^ 0xa5a55a5au; }";
        id<MTLLibrary> library = [device newLibraryWithSource:source options:nil error:&error];
        id<MTLFunction> function = [library newFunctionWithName:@"cug_fill"];
        if (!function) { fprintf(stderr, "FAIL: Metal compilation: %s\n", error.description.UTF8String); return 4; }
        id<MTLComputePipelineState> pipeline = [device newComputePipelineStateWithFunction:function error:&error];
        if (!pipeline) { fprintf(stderr, "FAIL: pipeline: %s\n", error.description.UTF8String); return 5; }
        const NSUInteger count = 4096;
        id<MTLBuffer> buffer = [device newBufferWithLength:count * sizeof(uint32_t) options:MTLResourceStorageModeShared];
        id<MTLCommandQueue> queue = [device newCommandQueue];
        id<MTLCommandBuffer> command = [queue commandBuffer];
        if (!buffer || !buffer.contents || !queue || !command) { fprintf(stderr, "FAIL: buffer/queue allocation.\n"); return 6; }
        memset(buffer.contents, 0, count * sizeof(uint32_t));
        id<MTLComputeCommandEncoder> encoder = [command computeCommandEncoder];
        if (!encoder) { fprintf(stderr, "FAIL: encoder allocation.\n"); return 7; }
        [encoder setComputePipelineState:pipeline];
        [encoder setBuffer:buffer offset:0 atIndex:0];
        NSUInteger group = MIN((NSUInteger)64, pipeline.maxTotalThreadsPerThreadgroup);
        if (!group) { fprintf(stderr, "FAIL: invalid threadgroup limit.\n"); return 8; }
        [encoder dispatchThreads:MTLSizeMake(count, 1, 1) threadsPerThreadgroup:MTLSizeMake(group, 1, 1)];
        [encoder endEncoding];
        dispatch_semaphore_t finished = dispatch_semaphore_create(0);
        [command addCompletedHandler:^(id<MTLCommandBuffer> done) { (void)done; dispatch_semaphore_signal(finished); }];
        [command commit];
        if (dispatch_semaphore_wait(finished, dispatch_time(DISPATCH_TIME_NOW, 30LL * NSEC_PER_SEC)) != 0) {
            fprintf(stderr, "FAIL: command completion timed out after 30 seconds.\n"); return 9;
        }
        if (command.status != MTLCommandBufferStatusCompleted) {
            fprintf(stderr, "FAIL: command status=%lu: %s\n", (unsigned long)command.status,
                    command.error.description.UTF8String); return 10;
        }
        const uint32_t *values = buffer.contents;
        for (NSUInteger i = 0; i < count; ++i) {
            uint32_t expected = ((uint32_t)i * 17u) ^ 0xa5a55a5au;
            if (values[i] != expected) {
                fprintf(stderr, "FAIL: result[%lu]=0x%08x expected 0x%08x\n", (unsigned long)i, values[i], expected);
                return 11;
            }
        }
        printf("PASS: %s completed Metal compute; all 4096 GPU-produced values verified.\n", device.name.UTF8String);
        printf("This test does not establish WindowServer acceleration or application compatibility.\n");
        return 0;
    }
}
