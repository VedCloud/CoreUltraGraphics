#ifndef XE_TRANSLATION_PIPELINE_H
#define XE_TRANSLATION_PIPELINE_H

#include <IOKit/IOService.h>
#include <IOKit/IOLib.h>
#include <IOKit/IOMemoryDescriptor.h>
#include <IOKit/IOBufferMemoryDescriptor.h>
#include <stdint.h>

// NOTE: kexts do not get a global operator new, so these classes are meant to be
// held by value (or embedded in an OSObject-derived class), never allocated with
// plain `new`. Copying is disabled because they own raw resources.

struct SpirvTokenStream { uint32_t *words; uint32_t wordCount; };

class AirToSpirvTranslator {
private:
    IOLock *parseLock;
    uint8_t *airCopy;
    uint32_t airLength;
    bool parsed;
public:
    AirToSpirvTranslator() : parseLock(IOLockAlloc()), airCopy(nullptr), airLength(0), parsed(false) {}
    ~AirToSpirvTranslator();
    AirToSpirvTranslator(const AirToSpirvTranslator &) = delete;
    AirToSpirvTranslator &operator=(const AirToSpirvTranslator &) = delete;

    // Not implemented yet: both return false so callers cannot mistake a stub for success.
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
    volatile uint32_t *ringHeadReg;   // left null unless hardware writes are enabled
    volatile uint32_t *ringTailReg;

    XeRingSubmission()
        : ringDesc(nullptr), ringMap(nullptr), ringBuffer(nullptr), headIdx(0), tailIdx(0),
          ringSizeDwords(0), lock(nullptr), ringHeadReg(nullptr), ringTailReg(nullptr) {}
    ~XeRingSubmission() { releaseResources(); }
    XeRingSubmission(const XeRingSubmission &) = delete;
    XeRingSubmission &operator=(const XeRingSubmission &) = delete;

    bool init(uint32_t sizeDwords);
    bool submitBatch(IOBufferMemoryDescriptor *batchBufferDesc, uint32_t dwords);
    void doorbell();
    void releaseResources();
};

class CoreUltraExecutionPipeline {
private:
    AirToSpirvTranslator shaderTranslator;
    XeRingSubmission renderRing;
    XeRingSubmission computeRing;
    volatile void *mmioBase;
    IOLock *swapLock;
    bool hwWritesEnabled;

    IOBufferMemoryDescriptor *frontDesc, *backDesc;
    IOMemoryMap *frontMap, *backMap;
    IOPhysicalAddress frontPhys, backPhys;
    uint32_t fbWidth, fbHeight, fbPitch;
    bool activeFront;

    void releaseSurfaces();

public:
    explicit CoreUltraExecutionPipeline(volatile void *mmio);
    ~CoreUltraExecutionPipeline();
    CoreUltraExecutionPipeline(const CoreUltraExecutionPipeline &) = delete;
    CoreUltraExecutionPipeline &operator=(const CoreUltraExecutionPipeline &) = delete;

    // Off by default. While off, nothing in this class writes to the GPU.
    // The register programming below is unverified for Meteor Lake; do not enable it
    // on real hardware until it has been checked against the display-v14 sources.
    void setHardwareWritesEnabled(bool enabled) { hwWritesEnabled = enabled; }

    bool initPipeline();
    bool allocateSurfaces(uint32_t width, uint32_t height);
    void handleDisplayVsync();
};

#endif