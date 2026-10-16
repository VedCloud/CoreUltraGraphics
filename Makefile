KEXT      = CoreUltraGraphics.kext
TARGET    = build/CoreUltraGraphics
OBJS      = build/CoreUltraGraphicsDriver.o
KMODINFO  = build/kmod_info.o
SDK       ?= $(shell xcrun --sdk macosx --show-sdk-path 2>/dev/null)
CXX       = $(shell xcrun -f clang++)
CC        = $(shell xcrun -f clang)

KERNEL_HEADERS = $(SDK)/System/Library/Frameworks/Kernel.framework/Headers
KERNEL_LIBS =
ifneq ($(strip $(KERNEL_SDK)),)
KERNEL_HEADERS = $(KERNEL_SDK)/Headers
KERNEL_LIBS = -L"$(KERNEL_SDK)/Library/x86_64"
endif
INC       = -isysroot "$(SDK)" -isystem "$(KERNEL_HEADERS)"

# Compile metadata with the same kernel-header set as the C++ source.
MACHINC   = $(INC)

CXXFLAGS  = -m64 -arch x86_64 -std=gnu++14 -fno-builtin -fno-exceptions -fno-rtti \
            -nostdinc -DKERNEL -DAPPLE -DNeXT -Wall -Wextra -O2 \
            -mkernel -fapple-kext -Wno-deprecated-declarations

.PHONY: all clean preflight

all: $(KEXT)

preflight:
	@test "$$(uname -s)" = Darwin || { echo "A macOS/Xcode build host is required."; exit 1; }
	@test -n "$(SDK)" -a -d "$(SDK)" || { echo "Select an installed macOS SDK with SDK=..."; exit 1; }
	@test -f "$(KERNEL_HEADERS)/IOKit/IOService.h" || { echo "Selected kernel SDK lacks required headers."; exit 1; }
	@test -f "$(KERNEL_HEADERS)/IOKit/pci/IOPCIDevice.h" || { echo "Selected kernel SDK lacks IOPCIFamily headers."; exit 1; }
	@xcrun --find clang++ >/dev/null
	@xcrun --find clang >/dev/null

$(OBJS) $(KMODINFO): | preflight

build/%.o: %.cpp CoreUltraGraphicsDriver.h port/mmio_probe_policy.h
	mkdir -p build
	$(CXX) $(CXXFLAGS) $(INC) -c $< -o $@

build/kmod_info.o: kmod_info.c
	mkdir -p build
	$(CC) -m64 -arch x86_64 -std=gnu11 -nostdinc -DKERNEL -DAPPLE -DNeXT -mkernel -fno-builtin -Wall -Wextra $(MACHINC) -c $< -o $@

# kmod_info.o must sit between -lkmodc++ and -lkmod (XNU libkern/kmod/README).
$(TARGET): $(OBJS) $(KMODINFO)
	mkdir -p build
	$(CXX) -arch x86_64 -isysroot "$(SDK)" -mkernel -fapple-kext -static -nostdlib $(KERNEL_LIBS) \
		-Xlinker -kext -Xlinker -no_deduplicate \
		$(OBJS) -lkmodc++ $(KMODINFO) -lkmod -lcc_kext \
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
	@if nm -gU $(TARGET) | grep -Eq '[[:space:]]_kmod_info$$'; then \
		echo "check-kmod-info: OK (_kmod_info present)"; \
	else \
		echo "check-kmod-info: FAIL -- _kmod_info missing from $(TARGET)."; \
		echo "  OpenCore cannot prelink-inject this kext. Do not deploy it."; \
		exit 1; \
	fi

clean:
	rm -rf build $(KEXT)
