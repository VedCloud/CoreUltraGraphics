KEXT      = CoreUltraGraphics.kext
TARGET    = build/CoreUltraGraphics
OBJS      = build/CoreUltraGraphicsDriver.o build/XeTranslationPipeline.o
SDK       = $(shell xcrun --sdk macosx --show-sdk-path)
CXX       = $(shell xcrun -f clang++)
CXXFLAGS  = -m64 -arch x86_64 -fno-builtin -fno-exceptions -fno-rtti -nostdinc -DKERNEL -DAPPLE -DNeXT -Wall -Wextra -O2 -mkernel
LDFLAGS   = -static -nostdlib -lkpi_iokit -lkpi_libkern -Xlinker -kext

all: $(KEXT)

build/%.o: %.cpp
	mkdir -p build
	$(CXX) $(CXXFLAGS) -c $< -o $@

$(TARGET): $(OBJS)
	$(CXX) $(CXXFLAGS) $(LDFLAGS) -o $@ $(OBJS)

$(KEXT): $(TARGET) Info.plist
	mkdir -p $(KEXT)/Contents/MacOS
	cp $(TARGET) $(KEXT)/Contents/MacOS/CoreUltraGraphics
	cp Info.plist $(KEXT)/Contents/Info.plist
	kextlibs -xml $(KEXT)
	plutil -lint $(KEXT)/Contents/Info.plist
	ls -lR $(KEXT)

clean:
	rm -rf build $(KEXT)
