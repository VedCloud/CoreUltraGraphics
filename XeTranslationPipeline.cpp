#include "XeTranslationPipeline.h"
#include <libkern/OSAtomic.h>

#define MI_BATCH_BUFFER_START 0x18800001
#define MI_NOOP 0x00000000
#define PLANE_CTL_A    0x70180
#define PLANE_STRIDE_A 0x70188
#define PLANE_SURF_A   0x7019C
#define PIPEASTAT      0x70024
#define PLANE_CTL_EN   (1u << 31)

#define SPV_MAGIC 0x07230203
#define SPV_VERSION 0x00010300
#define SPV_GENERATOR 0x000C0001

bool XeRingSubmission::init(uint32_t sizeDwords)
{
    if (sizeDwords < 512 || (sizeDwords & 63)) return false;
    ringSizeDwords = sizeDwords;
    ringDesc = IOBufferMemoryDescriptor::inTaskWithPhysicalMask(
        kernel_task, kIOMemoryUnshared | kIOMemoryPhysicallyContiguous, sizeDwords * sizeof(uint32_t), 0x00000000FFFFFFFFULL);
    if (!ringDesc) return false;
    if (ringDesc->prepare() != kIOReturnSuccess) { ringDesc->release(); ringDesc = nullptr; return false; }
    ringMap = ringDesc->map(kIOMapWriteCombine);
    if (!ringMap) { ringDesc->complete(); ringDesc->release(); ringDesc = nullptr; return false; }
    ringBuffer = (uint32_t*)ringMap->getVirtualAddress();
    bzero(ringBuffer, sizeDwords * sizeof(uint32_t));
    headIdx = 0; tailIdx = 0;
    lock = IOLockAlloc();
    return (lock != nullptr);
}

bool XeRingSubmission::submitBatch(IOBufferMemoryDescriptor *batchBufferDesc, uint32_t dwords)
{
    if (!batchBufferDesc || dwords == 0) return false;
    const uint32_t needed = dwords + 4;
    if (needed >= ringSizeDwords) return false;

    IOLockLock(lock);
    IOPhysicalAddress batchPhys = batchBufferDesc->getPhysicalAddress();
    uint32_t *src = (uint32_t *)batchBufferDesc->getBytesNoCopy();
    if (!batchPhys || !src) { IOLockUnlock(lock); return false; }

    uint32_t head = headIdx; uint32_t tail = tailIdx;
    uint32_t used = (tail >= head) ? (tail - head) : (ringSizeDwords - (head - tail));
    if (needed > (ringSizeDwords - used - 1)) { IOLockUnlock(lock); return false; }

    if (tail + needed > ringSizeDwords) {
        for (uint32_t i = tail; i < ringSizeDwords; i++) ringBuffer[i] = MI_NOOP;
        OSMemoryBarrier(); tail = 0;
    }

    ringBuffer[tail + 0] = MI_BATCH_BUFFER_START;
    ringBuffer[tail + 1] = (uint32_t)(batchPhys & 0xFFFFFFFF);
    ringBuffer[tail + 2] = (uint32_t)(batchPhys >> 32);
    ringBuffer[tail + 3] = 0x00000000;
    for (uint32_t i = 0; i < dwords; i++) ringBuffer[tail + 4 + i] = src[i];

    OSMemoryBarrier();
    tailIdx = (tail + needed) % ringSizeDwords;
    IOLockUnlock(lock);
    doorbell();
    return true;
}

void XeRingSubmission::doorbell()
{
    if (ringTailReg) {
        OSWriteLittleInt32((void*)ringTailReg, 0, tailIdx * sizeof(uint32_t));
        OSMemoryBarrier();
    }
}

bool CoreUltraExecutionPipeline::initPipeline()
{
    if (!mmioBase) return false;
    renderRing = new XeRingSubmission(); computeRing = new XeRingSubmission();
    if (!renderRing || !computeRing) return false;
    if (!renderRing->init(4096) || !computeRing->init(4096)) return false;

    renderRing->ringHeadReg = (volatile uint32_t *)((uint8_t *)mmioBase + 0x2030);
    renderRing->ringTailReg = (volatile uint32_t *)((uint8_t *)mmioBase + 0x2030 + 4);
    computeRing->ringHeadReg = (volatile uint32_t *)((uint8_t *)mmioBase + 0x1A030);
    computeRing->ringTailReg = (volatile uint32_t *)((uint8_t *)mmioBase + 0x1A030 + 4);
    return true;
}

bool CoreUltraExecutionPipeline::allocateSurfaces(uint32_t width, uint32_t height)
{
    uint32_t size = width * height * 4;
    IOLockLock(swapLock);
    for (int i = 0; i < 2; i++) {
        IOBufferMemoryDescriptor *desc = IOBufferMemoryDescriptor::inTaskWithPhysicalMask(
            kernel_task, kIOMemoryUnshared | kIOMemoryPhysicallyContiguous, size, 0x00000000FFFFFFFFULL);
        IOMemoryMap *map = desc->map(kIOMapWriteCombine);
        if (i == 0) { frontDesc = desc; frontMap = map; frontPhys = desc->getPhysicalAddress(); }
        else        { backDesc = desc; backMap = map; backPhys = desc->getPhysicalAddress(); }
    }
    fbWidth = width; fbHeight = height; fbPitch = width * 4;
    volatile uint8_t *mmio = (volatile uint8_t *)mmioBase;
    OSWriteLittleInt32((void*)(mmio + PLANE_STRIDE_A), 0, fbPitch);
    OSWriteLittleInt32((void*)(mmio + PLANE_SURF_A), 0, (uint32_t)(frontPhys & 0xFFFFFFFF));
    uint32_t ctl = OSReadLittleInt32((void*)(mmio + PLANE_CTL_A), 0) | PLANE_CTL_EN | (1u << 10);
    OSWriteLittleInt32((void*)(mmio + PLANE_CTL_A), 0, ctl & ~(1u << 6));
    activeFront = true; IOLockUnlock(swapLock);
    return true;
}

void CoreUltraExecutionPipeline::handleDisplayVsync()
{
    volatile uint8_t *mmio = (volatile uint8_t *)mmioBase;
    if (!(OSReadLittleInt32((void*)(mmio + PIPEASTAT), 0) & (1u << 1))) return;
    IOLockLock(swapLock);
    IOPhysicalAddress newFront = activeFront ? backPhys : frontPhys;
    OSWriteLittleInt32((void*)(mmio + PLANE_SURF_A), 0, (uint32_t)(newFront & 0xFFFFFFFF));
    OSMemoryBarrier(); activeFront = !activeFront; IOLockUnlock(swapLock);
}

bool AirToSpirvTranslator::parseAir(const uint8_t *airBinary, uint32_t length) { return true; }
bool AirToSpirvTranslator::emitSpirvForXeLPG(SpirvTokenStream &out) { return true; }
