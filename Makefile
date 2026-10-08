KEXT      = CoreUltraGraphics.kext
TARGET    = build/CoreUltraGraphics
OBJS      = build/CoreUltraGraphicsDriver.o build/XeTranslationPipeline.o
SDK       = /Applications/Xcode_15.4.app/Contents/Developer/Platforms/MacOSX.platform/Developer/SDKs/MacOSX14.5.sdk
CXX       = $(shell xcrun -f clang++)

INC       = -isysroot $(SDK) -isystem $(SDK)/System/Library/Frameworks/Kernel.framework/Headers

CXXFLAGS  = -m64 -arch x86_64 -std=gnu++14 -fno-builtin -fno-exceptions -fno-rtti \
            -nostdinc -DKERNEL -DAPPLE -DNeXT -Wall -Wextra -O2 \
            -mkernel -fapple-kext -Wno-deprecated-declarations

.PHONY: all clean

all: $(KEXT)

build/%.o: %.cpp
	mkdir -p build
	$(CXX) $(CXXFLAGS) $(INC) -c $< -o $@

$(TARGET): $(OBJS)
	mkdir -p build
	$(CXX) -arch x86_64 -isysroot $(SDK) -mkernel -fapple-kext -static -nostdlib \
		-Xlinker -kext -Xlinker -no_deduplicate \
		$(OBJS) -lkmodc++ -lkmod -lcc_kext \
		-o $@

$(KEXT): $(TARGET) Info.plist
	mkdir -p $(KEXT)/Contents/MacOS
	cp $(TARGET) $(KEXT)/Contents/MacOS/CoreUltraGraphics
	cp Info.plist $(KEXT)/Contents/Info.plist
	plutil -lint $(KEXT)/Contents/Info.plist
	@$(MAKE) --no-print-directory check-kmod-info

# OpenCore's prelinked injection requires the _kmod_info symbol. Without it,
# KextFindKmodAddress() returns Kmod = 0, so InternalPrelinkKext() bails out at
# Link.c:1629 with EFI_UNSUPPORTED, InternalLinkPrelinkedKext() returns NULL, and
# PrelinkedInjectKext() reports EFI_INVALID_PARAMETER with no further detail.
# A missing _kmod_info therefore fails silently at boot -- fail the build instead.
.PHONY: check-kmod-info
check-kmod-info:
	@if nm -g $(TARGET) 2>/dev/null | grep -q '_kmod_info'; then \
		echo "check-kmod-info: OK (_kmod_info present)"; \
	else \
		echo "check-kmod-info: FAIL -- _kmod_info missing from $(TARGET)."; \
		echo "  OpenCore cannot prelink-inject this kext. Do not deploy it."; \
		exit 1; \
	fi

clean:
	rm -rf build $(KEXT)