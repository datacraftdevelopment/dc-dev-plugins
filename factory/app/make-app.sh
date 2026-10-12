#!/usr/bin/env bash
# Build RunwayBar in release mode and wrap it in build/Runway.app (menu bar only, no Dock icon).
#   bash make-app.sh            # build only
#   bash make-app.sh --install  # build, copy to /Applications/Runway.app (quitting a running copy) and open it
set -euo pipefail
INSTALL=0; [ "${1:-}" = "--install" ] && INSTALL=1
cd "$(dirname "$0")"

APP="build/Runway.app"

swift build -c release
BIN="$(swift build -c release --show-bin-path)/RunwayBar"

VERSION="$(tr -d '[:space:]' < VERSION)"
# CFBundleVersion only ever goes up: the commit count on main (this checkout's HEAD if main isn't a local ref).
BUILD="$(git rev-list --count main 2>/dev/null || git rev-list --count HEAD)"
FEED_URL="https://github.com/datacraftdevelopment/dc-dev-plugins/releases/latest/download/appcast.xml"
# The public key is committed and isn't secret. No key file means the updater is off, and the menu says so.
PUBKEY=""; [ -f sparkle-public-key ] && PUBKEY="$(tr -d '[:space:]' < sparkle-public-key)"
SPARKLE_KEYS=""
if [ -n "$PUBKEY" ]; then
  SPARKLE_KEYS="  <key>SUFeedURL</key><string>$FEED_URL</string>
  <key>SUPublicEDKey</key><string>$PUBKEY</string>
  <key>SUEnableAutomaticChecks</key><true/>
  <key>SUScheduledCheckInterval</key><integer>86400</integer>"
else
  echo "note: no sparkle-public-key, so the updater is off in this build"
fi

rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS"
cp "$BIN" "$APP/Contents/MacOS/Runway"

# Sparkle's framework rides in Contents/Frameworks; the binary finds it through an rpath.
mkdir -p "$APP/Contents/Frameworks"
cp -R "$(dirname "$BIN")/Sparkle.framework" "$APP/Contents/Frameworks/"
install_name_tool -add_rpath @executable_path/../Frameworks "$APP/Contents/MacOS/Runway"

# SwiftPM resource bundles (SwiftTerm's Metal shaders) ride in Contents/Resources, where SwiftTerm looks for them.
mkdir -p "$APP/Contents/Resources"
for bundle in "$(dirname "$BIN")"/*.bundle; do
  [ -e "$bundle" ] && cp -R "$bundle" "$APP/Contents/Resources/"
done

cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>Runway</string>
  <key>CFBundleDisplayName</key><string>Runway</string>
  <key>CFBundleIdentifier</key><string>dev.datacraft.runway</string>
  <key>CFBundleExecutable</key><string>Runway</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>$VERSION</string>
  <key>CFBundleVersion</key><string>$BUILD</string>
  <key>LSMinimumSystemVersion</key><string>14.0</string>
  <key>LSUIElement</key><true/>
  <key>NSHighResolutionCapable</key><true/>
$SPARKLE_KEYS
</dict>
</plist>
PLIST

# Ad-hoc sign so macOS will launch it locally.
codesign --force --deep --sign - "$APP" >/dev/null 2>&1 || echo "warning: ad-hoc codesign failed"

ABS="$(cd "$(dirname "$APP")" && pwd)/$(basename "$APP")"

if [ "$INSTALL" = 1 ]; then
  pkill -x Runway 2>/dev/null || true
  rm -rf /Applications/Runway.app
  cp -R "$APP" /Applications/Runway.app
  open /Applications/Runway.app
  echo "Installed /Applications/Runway.app and opened it"
  echo "Login Items: System Settings > General > Login Items & Extensions > '+' > pick /Applications/Runway.app"
  exit 0
fi
echo "Built $ABS"
echo "Run it:    open \"$ABS\""
echo "Login Items: System Settings > General > Login Items & Extensions > '+' > pick $ABS"
