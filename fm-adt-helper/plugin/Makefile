# ADT Helper — FileMaker plug-in (shipped copy)
# Most installs never build: `make install-prebuilt` copies prebuilt/ into
# FileMaker's Extensions. Building from source needs the Claris Plug-In SDK
# (claris.com/resources/downloads, bottom of page) unzipped somewhere and
# pointed at via SDK=.
SDK     ?= $(HOME)/Claris/PlugInSDK
BUILD   := build
BUNDLE  := $(BUILD)/ADT Helper.fmplugin
BINARY  := $(BUNDLE)/Contents/MacOS/ADT_Helper
EXTDIR  := $(HOME)/Library/Application Support/FileMaker/FileMaker Pro/26.0/Extensions

all: bundle

bundle: src/ADTHelper.mm Info.plist
	mkdir -p "$(BUNDLE)/Contents/MacOS"
	clang++ -std=c++17 -ObjC++ -bundle -fobjc-arc \
	  -mmacosx-version-min=14.0 -arch arm64 \
	  -I"$(SDK)/Headers" -F"$(SDK)/Libraries/Mac" \
	  -framework FMWrapper -framework Cocoa -framework WebKit \
	  -o "$(BINARY)" src/ADTHelper.mm
	cp Info.plist "$(BUNDLE)/Contents/Info.plist"
	codesign --force --sign - "$(BUNDLE)"
	@echo "Built: $(BUNDLE)"

install: bundle
	rm -rf "$(EXTDIR)/ADT Helper.fmplugin"
	cp -R "$(BUNDLE)" "$(EXTDIR)/"
	@echo "Installed — restart FileMaker Pro to load."

install-prebuilt:
	rm -rf "$(EXTDIR)/ADT Helper.fmplugin"
	cp -R "prebuilt/ADT Helper.fmplugin" "$(EXTDIR)/"
	@echo "Installed prebuilt bundle — restart FileMaker Pro to load."

clean:
	rm -rf "$(BUILD)"
