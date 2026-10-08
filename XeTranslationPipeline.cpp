#include "XeTranslationPipeline.h"
#include <libkern/OSAtomic.h>

#define MI_BATCH_BUFFER_START 0x18800001
#define MI_NOOP 0x00000000

// Intel engine register layout: RING_TAIL = base + 0x30, RING_HEAD = base + 0x34.
// (The previous code had these two swapped.) Gen12+ normally submits through
// execlists/GuC rather than legacy ring-tail writes, so this stays dormant.
#define RCS0_RING_BASE 0x2000
#define CCS0_RING_BASE 0x1A000
#define RING_TAIL_OFF  0x30
#define RING_HEAD_OFF  0x34
#define RING_HEAD_ADDR_MASK 0x001FFFFCu

#define PLANE_CTL_A    0x70180
#define PLANE_STRIDE_A 0x70188
#define PLANE_SURF_A   0x7019C
#define PIPEASTAT      0x70024
#define PLANE_CTL_EN   (1u << 31)

#define XE_MEMORY_BARRIER() asm volatile("mfence" ::: "memory")

// ---------------------------------------------------------------- translator

AirToSpirvTranslator::~AirToSpirvTranslator()
{
    if (airCopy) { IOFree(airCopy, airLength); airCopy = nullptr; airLength = 0; }
    if (parseLock) { IOLockFree(parseLock); parseLock = nullptr; }
}

bool AirToSpirvTranslator::parseAir(const uint8_t *, uint32_t)
{
    parsed = false;
    return false;   // not implemented
}

bool AirToSpirvTranslator::emitSpirvForXeLPG(SpirvTokenStream &out)
{
    out.words = nullptr;
    out.wordCount = 0;
    return false;   // not implemented
}

// ---------------------------------------------------------------- ring

void XeRingSubmission::releaseResources()
{
    ringBuffer = nullptr;
    ringHeadReg = nullptr;
    ringTailReg = nullptr;
    if (ringMap) { ringMap->release(); ringMap = nullptr; }
    if (ringDesc) { ringDesc->complete(); ringDesc->release(); ringDesc = nullptr; }
    if (lock) { IOLockFree(lock); lock = nullptr; }
    headIdx = tailIdx = ringSizeDwords = 0;
}

bool XeRingSubmission::init(uint32_t sizeDwords)
{
    if (ringDesc) return false;   // already initialised
    if (sizeDwords < 512 || (sizeDwords & 63)) return false;

    ringDesc = IOBufferMemoryDescriptor::inTaskWithPhysicalMask(
        kernel_task, kIOMemoryUnshared | kIOMemoryPhysicallyContiguous,
        sizeDwords * sizeof(uint32_t), 0x00000000FFFFF000ULL);
    if (!ringDesc) return false;

    if (ringDesc->prepare() != kIOReturnSuccess) {
        ringDesc->release(); ringDesc = nullptr;
        return false;
    }
    ringMap = ringDesc->map(kIOMapWriteCombineCache);
    if (!ringMap) { releaseResources(); return false; }

    ringBuffer = (uint32_t *)ringMap->getVirtualAddress();
    ringSizeDwords = sizeDwords;
    bzero(ringBuffer, sizeDwords * sizeof(uint32_t));
    headIdx = 0;
    tailIdx = 0;
    lock = IOLockAlloc();
    if (!lock) { releaseResources(); return false; }
    return true;
}

// The batch is referenced by address only; its contents are NOT copied into the ring.
// The address emitted here is a CPU physical address. A real GPU needs a GGTT/PPGTT
// address, so this will not execute on hardware until a GPU address space exists.
bool XeRingSubmission::submitBatch(IOBufferMemoryDescriptor *batchBufferDesc, uint32_t dwords)
{
    if (!ringBuffer || !lock || !batchBufferDesc || dwords == 0) return false;
    if ((uint64_t)dwords * sizeof(uint32_t) > batchBufferDesc->getLength()) return false;

    IOPhysicalAddress batchPhys = batchBufferDesc->getPhysicalAddress();
    if (!batchPhys) return false;

    const uint32_t needed = 4;   // MI_BATCH_BUFFER_START (3 dwords) + 1 pad to stay qword aligned

    IOLockLock(lock);

    uint32_t head = headIdx;
    if (ringHeadReg) {
        head = (OSReadLittleInt32((const volatile void *)ringHeadReg, 0) & RING_HEAD_ADDR_MASK) / 4;
        if (head >= ringSizeDwords) head = headIdx;
        headIdx = head;
    }
    uint32_t tail = tailIdx;

    // Dwords of padding needed to wrap, counted against free space.
    uint32_t pad = (tail + needed > ringSizeDwords) ? (ringSizeDwords - tail) : 0;
    uint32_t freeDwords = (head + ringSizeDwords - tail - 1) % ringSizeDwords;
    if (pad + needed > freeDwords) { IOLockUnlock(lock); return false; }

    if (pad) {
        for (uint32_t i = tail; i < ringSizeDwords; i++) ringBuffer[i] = MI_NOOP;
        tail = 0;
    }

    ringBuffer[tail + 0] = MI_BATCH_BUFFER_START;
    ringBuffer[tail + 1] = (uint32_t)(batchPhys & 0xFFFFFFFF);
    ringBuffer[tail + 2] = (uint32_t)((uint64_t)batchPhys >> 32);
    ringBuffer[tail + 3] = MI_NOOP;

    XE_MEMORY_BARRIER();
    tailIdx = (tail + needed) % ringSizeDwords;
    doorbell();   // no-op unless the tail register was wired up
    IOLockUnlock(lock);
    return true;
}

void XeRingSubmission::doorbell()
{
    if (ringTailReg) {
        OSWriteLittleInt32((volatile void *)ringTailReg, 0, tailIdx * sizeof(uint32_t));
        XE_MEMORY_BARRIER();
    }
}

// ---------------------------------------------------------------- pipeline

CoreUltraExecutionPipeline::CoreUltraExecutionPipeline(volatile void *mmio)
    : mmioBase(mmio), swapLock(IOLockAlloc()), hwWritesEnabled(false),
      frontDesc(nullptr), backDesc(nullptr), frontMap(nullptr), backMap(nullptr),
      frontPhys(0), backPhys(0), fbWidth(0), fbHeight(0), fbPitch(0), activeFront(true)
{
}

CoreUltraExecutionPipeline::~CoreUltraExecutionPipeline()
{
    releaseSurfaces();
    if (swapLock) { IOLockFree(swapLock); swapLock = nullptr; }
}

bool CoreUltraExecutionPipeline::initPipeline()
{
    if (!mmioBase || !swapLock) return false;
    if (!renderRing.init(4096)) return false;
    if (!computeRing.init(4096)) { renderRing.releaseResources(); return false; }

    // Only wire the doorbell registers when hardware writes are explicitly enabled.
    if (hwWritesEnabled) {
        volatile uint8_t *mmio = (volatile uint8_t *)mmioBase;
        renderRing.ringTailReg  = (volatile uint32_t *)(mmio + RCS0_RING_BASE + RING_TAIL_OFF);
        renderRing.ringHeadReg  = (volatile uint32_t *)(mmio + RCS0_RING_BASE + RING_HEAD_OFF);
        computeRing.ringTailReg = (volatile uint32_t *)(mmio + CCS0_RING_BASE + RING_TAIL_OFF);
        computeRing.ringHeadReg = (volatile uint32_t *)(mmio + CCS0_RING_BASE + RING_HEAD_OFF);
    }
    return true;
}

static bool allocSurface(uint32_t size, IOBufferMemoryDescriptor **descOut,
                         IOMemoryMap **mapOut, IOPhysicalAddress *physOut)
{
    IOBufferMemoryDescriptor *desc = IOBufferMemoryDescriptor::inTaskWithPhysicalMask(
        kernel_task, kIOMemoryUnshared | kIOMemoryPhysicallyContiguous, size, 0x00000000FFFFF000ULL);
    if (!desc) return false;
    if (desc->prepare() != kIOReturnSuccess) { desc->release(); return false; }
    IOMemoryMap *map = desc->map(kIOMapWriteCombineCache);
    if (!map) { desc->complete(); desc->release(); return false; }
    *descOut = desc;
    *mapOut = map;
    *physOut = desc->getPhysicalAddress();
    return true;
}

void CoreUltraExecutionPipeline::releaseSurfaces()
{
    if (frontMap)  { frontMap->release();  frontMap = nullptr; }
    if (backMap)   { backMap->release();   backMap = nullptr; }
    if (frontDesc) { frontDesc->complete(); frontDesc->release(); frontDesc = nullptr; }
    if (backDesc)  { backDesc->complete();  backDesc->release();  backDesc = nullptr; }
    frontPhys = backPhys = 0;
}

bool CoreUltraExecutionPipeline::allocateSurfaces(uint32_t width, uint32_t height)
{
    if (!mmioBase || !swapLock) return false;
    if (width == 0 || height == 0 || width > 16384 || height > 16384) return false;
    const uint32_t size = width * height * 4;

    IOLockLock(swapLock);
    releaseSurfaces();
    bool ok = allocSurface(size, &frontDesc, &frontMap, &frontPhys) &&
              allocSurface(size, &backDesc,  &backMap,  &backPhys);
    if (!ok) {
        releaseSurfaces();
        IOLockUnlock(swapLock);
        return false;
    }
    fbWidth = width; fbHeight = height; fbPitch = width * 4;
    activeFront = true;

    // UNVERIFIED for Meteor Lake and uses CPU physical addresses where the display
    // engine expects GGTT offsets. Gated off by default.
    if (hwWritesEnabled) {
        volatile uint8_t *mmio = (volatile uint8_t *)mmioBase;
        OSWriteLittleInt32((volatile void *)(mmio + PLANE_STRIDE_A), 0, fbPitch);
        OSWriteLittleInt32((volatile void *)(mmio + PLANE_SURF_A), 0, (uint32_t)(frontPhys & 0xFFFFFFFF));
        uint32_t ctl = OSReadLittleInt32((const volatile void *)(mmio + PLANE_CTL_A), 0) | PLANE_CTL_EN;
        OSWriteLittleInt32((volatile void *)(mmio + PLANE_CTL_A), 0, ctl);
    }
    IOLockUnlock(swapLock);
    return true;
}

void CoreUltraExecutionPipeline::handleDisplayVsync()
{
    if (!hwWritesEnabled || !mmioBase || !swapLock || !frontPhys || !backPhys) return;
    volatile uint8_t *mmio = (volatile uint8_t *)mmioBase;
    // Legacy pre-gen9 status register; newer display engines use the DE_PIPE interrupt registers.
    if (!(OSReadLittleInt32((const volatile void *)(mmio + PIPEASTAT), 0) & (1u << 1))) return;

    IOLockLock(swapLock);
    IOPhysicalAddress newFront = activeFront ? backPhys : frontPhys;
    OSWriteLittleInt32((volatile void *)(mmio + PLANE_SURF_A), 0, (uint32_t)(newFront & 0xFFFFFFFF));
    XE_MEMORY_BARRIER();
    activeFront = !activeFront;
    IOLockUnlock(swapLock);
}