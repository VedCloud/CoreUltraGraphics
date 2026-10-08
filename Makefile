KEXT      = CoreUltraGraphics.kext
TARGET    = build/CoreUltraGraphics
OBJS      = build/CoreUltraGraphicsDriver.o build/XeTranslationPipeline.o
SDK       = $(shell xcrun --sdk macosx --show-sdk-path)
CXX       = $(shell xcrun -f clang++)

# Core System Header and KPI Framework Vector Inclusions
INC       = -isysroot $(SDK) -I$(SDK)/System/Library/Frameworks/Kernel.framework/Headers

CXXFLAGS  = -m64 -arch x86_64 -fno-builtin -fno-exceptions -fno-rtti -nostdinc -DKERNEL -DAPPLE -DNeXT -Wall -Wextra -O2 -mkernel
LDFLAGS   = -static -nostdlib -lkpi_iokit -lkpi_libkern -Xlinker -kext

all: $(KEXT)

build/%.o: %.cpp
	mkdir -p build
	$(CXX) $(CXXFLAGS) $(INC) -c $< -o $@

$(TARGET): $(OBJS)
	$(CXX) $(CXXFLAGS) $(LDFLAGS) -o $@ $(OBJS)

$(KEXT): $(TARGET) Info.plist
	mkdir -p $(KEXT)/Contents/MacOS
	cp $(TARGET) $(KEXT)/Contents/MacOS/CoreUltraGraphics
	cp Info.plist $(KEXT)/Contents/Info.plist
	plutil -lint $(KEXT)/Contents/Info.plist

clean:
	rm -rf build $(KEXT)
