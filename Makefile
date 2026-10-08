KEXT      = CoreUltraGraphics.kext
TARGET    = build/CoreUltraGraphics
OBJS      = build/CoreUltraGraphicsDriver.o build/XeTranslationPipeline.o
SDK       = $(shell xcrun --sdk macosx --show-sdk-path)
CXX       = $(shell xcrun -f clang++)

# Target clean include environments and standard GNU structures
INC       = -isysroot $(SDK) -I$(SDK)/System/Library/Frameworks/Kernel.framework/Headers

# Core kernel compilation configurations with explicit dialect tracking
CXXFLAGS  = -m64 -arch x86_64 -std=gnu++14 -fno-builtin -fno-exceptions -fno-rtti -nostdinc -DKERNEL -DAPPLE -DNeXT -Wall -Wextra -O2 -mkernel
LDFLAGS   = -static -nostdlib -Xlinker -kext \
            -F/Applications/Xcode_15.4.app/Contents/Developer/Platforms/MacOSX.platform/Developer/SDKs/MacOSX14.5.sdk/System/Library/Frameworks \
            -framework Kernel

all: $(KEXT)

build/%.o: %.cpp
	mkdir -p build
	$(CXX) $(CXXFLAGS) $(INC) -c $< -o $@

$(TARGET): $(OBJS)
	mkdir -p build
	$(CXX) -arch x86_64 -mkernel $(LDFLAGS) -o $@ $(OBJS)

$(KEXT): $(TARGET) Info.plist
	mkdir -p $(KEXT)/Contents/MacOS
	cp $(TARGET) $(KEXT)/Contents/MacOS/CoreUltraGraphics
	cp Info.plist $(KEXT)/Contents/Info.plist
	plutil -lint $(KEXT)/Contents/Info.plist

clean:
	rm -rf build $(KEXT)