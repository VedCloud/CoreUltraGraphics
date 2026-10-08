#ifndef XeTranslationPipeline_h
#define XeTranslationPipeline_h

#include <IOKit/IOService.h>
#include <IOKit/IOLib.h>
#include <IOKit/IOMemoryDescriptor.h>
#include <IOKit/IOMemoryMap.h>
#include <IOKit/graphics/IOFramebuffer.h>
#include <IOKit/IOBufferMemoryDescriptor.h>
#include <stdint.h>

struct SpirvTokenStream { uint32_t *words; uint32_t wordCount; };

class AirToSpirvTranslator {
private:
    IOLock *parseLock;
    uint8_t *airCopy;
    uint32_t airLength;
    uint32_t bound;
    bool parsed;
    bool hasAlu;
    bool hasTex;
    bool hasBarrier;
public:
    AirToSpirvTranslator() : parseLock(IOLockAlloc()), airCopy(nullptr), airLength(0), bound(0), parsed(false) {}
    bool parseAir(const uint8_t *airBinary, uint32_t length);
    bool emitSpirvForXeLPG(SpirvTokenStream &out);
};

class XeRingSubmission {
public:
    IOBufferMemoryDescriptor *ringDesc;
    IOMemoryMap *ringMap;
    uint32_t *ringBuffer;
    uint32_t headIdx;
    uint32_t tailIdx;
    uint32_t ringSizeDwords;
    IOLock *lock;
    volatile uint32_t *ringHeadReg;
    volatile uint32_t *ringTailReg;

    bool init(uint32_t sizeDwords);
    bool submitBatch(IOBufferMemoryDescriptor *batchBufferDesc, uint32_t dwords);
    void doorbell();
    void releaseResources() {
        if (ringMap) ringMap->release();
        if (ringDesc) ringDesc->release();
    }
};

class CoreUltraExecutionPipeline {
private:
    AirToSpirvTranslator *shaderTranslator;
    XeRingSubmission *renderRing;
    XeRingSubmission *computeRing;
    IOFramebuffer *framebufferHook;
    volatile void *mmioBase;
    IOLock *swapLock;

    IOBufferMemoryDescriptor *frontDesc, *backDesc;
    IOMemoryMap *frontMap, *backMap;
    IOPhysicalAddress frontPhys, backPhys;
    uint32_t fbWidth, fbHeight, fbPitch;
    bool activeFront;

public:
    bool initPipeline();
    bool allocateSurfaces(uint32_t width, uint32_t height);
    void handleDisplayVsync();
};

#endif