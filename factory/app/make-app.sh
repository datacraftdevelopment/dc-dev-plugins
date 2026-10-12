#!/usr/bin/env bash
# Build RunwayBar in release mode and wrap it in build/Runway.app (menu bar only, no Dock icon).
#   bash make-app.sh            # build only
#   bash make-app.sh --install  # build, copy to /Applications/Runway.app (quitting a running copy) and open it
#   bash make-app.sh --release  # Joe only: sign, notarize, staple, zip, Sparkle-sign, write appcast.xml, gh release create
#   bash make-app.sh --release --dry-run  # all of that except notarize and publish; output in build/release/
# --release reads RUNWAY_SIGN_IDENTITY (Developer ID Application name), RUNWAY_NOTARY_PROFILE (notarytool keychain
# profile) and optionally SPARKLE_SIGN_UPDATE (path to Sparkle's sign_update). None has a default.
set -euo pipefail
INSTALL=0; RELEASE=0; DRY=0
for arg in "$@"; do
  case "$arg" in
    --install) INSTALL=1 ;;
    --release) RELEASE=1 ;;
    --dry-run) DRY=1 ;;
    *) echo "make-app.sh: unknown option $arg" >&2; exit 2 ;;
  esac
done
[ "$DRY" = 1 ] && [ "$RELEASE" = 0 ] && { echo "make-app.sh: --dry-run only goes with --release" >&2; exit 2; }
[ "$INSTALL" = 1 ] && [ "$RELEASE" = 1 ] && { echo "make-app.sh: --install and --release don't mix" >&2; exit 2; }
cd "$(dirname "$0")"

APP="build/Runway.app"
REPO="$(git rev-parse --show-toplevel)"
TAG="runway-app-v$(tr -d '[:space:]' < VERSION)"
REL_DIR="build/release"

die() { echo "make-app.sh: $*" >&2; exit 1; }
# A real release stops on a refusal. A dry run reports it and carries on, so an agent in a worktree can test the rest.
refuse() {
  if [ "$DRY" = 1 ]; then echo "make-app.sh: would refuse: $*" >&2; else die "refusing to release: $*"; fi
}

if [ "$RELEASE" = 1 ]; then
  [ -z "$(git -C "$REPO" status --porcelain)" ] || refuse "working tree is dirty (commit or stash first)"
  BRANCH="$(git -C "$REPO" rev-parse --abbrev-ref HEAD)"
  [ "$BRANCH" = main ] || refuse "not on main (on $BRANCH)"
  [ -n "${RUNWAY_SIGN_IDENTITY:-}" ] || die "RUNWAY_SIGN_IDENTITY is not set (the Developer ID Application identity to sign with)"
  [ "$DRY" = 1 ] || [ -n "${RUNWAY_NOTARY_PROFILE:-}" ] || die "RUNWAY_NOTARY_PROFILE is not set (the notarytool keychain profile)"
  [ -s sparkle-public-key ] || die "factory/app/sparkle-public-key is missing; run Sparkle's generate_keys and commit the public key"
  if gh release view "$TAG" >/dev/null 2>&1; then refuse "$TAG already exists as a GitHub release"; fi
  echo "== check"
  CHECK_CMD="${RUNWAY_RELEASE_CHECK_CMD:-bash $REPO/factory/scripts/check.sh}"
  bash -c "$CHECK_CMD" || refuse "check failed ($CHECK_CMD)"
fi

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

if [ "$RELEASE" = 1 ]; then
  # Developer ID plus the hardened runtime. A dry run skips the secure timestamp (it needs Apple's server).
  TS="--timestamp"; [ "$DRY" = 1 ] && TS="--timestamp=none"
  codesign --force --deep --options runtime "$TS" --sign "$RUNWAY_SIGN_IDENTITY" "$APP" \
    || die "codesign failed (is the identity in this Mac's keychain? RUNWAY_SIGN_IDENTITY=$RUNWAY_SIGN_IDENTITY)"
  codesign --verify --deep --strict "$APP" || die "signature verification failed"
else
  # Ad-hoc sign so macOS will launch it locally.
  codesign --force --deep --sign - "$APP" >/dev/null 2>&1 || echo "warning: ad-hoc codesign failed"
fi

if [ "$RELEASE" = 1 ]; then
  rm -rf "$REL_DIR"; mkdir -p "$REL_DIR"
  ZIP="$REL_DIR/Runway-$VERSION.zip"
  if [ "$DRY" = 1 ]; then
    echo "== dry run: skipping notarize and staple"
  else
    echo "== notarize"
    ditto -c -k --keepParent "$APP" "$REL_DIR/notarize.zip"
    xcrun notarytool submit "$REL_DIR/notarize.zip" --keychain-profile "$RUNWAY_NOTARY_PROFILE" --wait \
      || die "notarization failed"
    rm -f "$REL_DIR/notarize.zip"
    xcrun stapler staple "$APP" || die "stapling failed"
  fi
  ditto -c -k --keepParent "$APP" "$ZIP"

  SIGN_UPDATE="${SPARKLE_SIGN_UPDATE:-$(find .build/artifacts -name sign_update -type f -perm -u+x 2>/dev/null | head -n 1)}"
  [ -n "$SIGN_UPDATE" ] && [ -x "$SIGN_UPDATE" ] || die "Sparkle's sign_update not found (set SPARKLE_SIGN_UPDATE, or run swift build so the package's artifacts exist)"
  # Prints: sparkle:edSignature="..." length="..." ; the private key comes from this Mac's keychain.
  SIG="$("$SIGN_UPDATE" "$ZIP")" || die "sign_update failed (is the Sparkle private key in this Mac's keychain? see generate_keys)"
  case "$SIG" in *sparkle:edSignature=*) ;; *) die "sign_update gave no signature" ;; esac
  SIG="$(printf '%s' "$SIG" | tr -d '\n')"

  cat > "$REL_DIR/appcast.xml" <<APPCAST
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:sparkle="http://www.andymatuschak.org/xml-namespaces/sparkle">
  <channel>
    <title>Runway</title>
    <item>
      <title>Runway $VERSION</title>
      <pubDate>$(LC_ALL=C date -u "+%a, %d %b %Y %H:%M:%S +0000")</pubDate>
      <sparkle:version>$BUILD</sparkle:version>
      <sparkle:shortVersionString>$VERSION</sparkle:shortVersionString>
      <sparkle:minimumSystemVersion>14.0</sparkle:minimumSystemVersion>
      <enclosure url="https://github.com/datacraftdevelopment/dc-dev-plugins/releases/download/$TAG/Runway-$VERSION.zip" type="application/octet-stream" $SIG/>
    </item>
  </channel>
</rss>
APPCAST
  if [ "$DRY" = 1 ]; then
    echo "Dry run done: $(pwd)/$ZIP and $(pwd)/$REL_DIR/appcast.xml (not notarized, not published)"
    exit 0
  fi
  echo "== publish $TAG"
  gh release create "$TAG" "$ZIP" "$REL_DIR/appcast.xml" --target "$(git -C "$REPO" rev-parse HEAD)" \
    --title "Runway $VERSION" --notes "Runway app $VERSION (build $BUILD)." || die "gh release create failed"
  echo "Published $TAG"
  exit 0
fi

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
