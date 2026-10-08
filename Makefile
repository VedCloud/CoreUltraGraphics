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

clean:
	rm -rf build $(KEXT)