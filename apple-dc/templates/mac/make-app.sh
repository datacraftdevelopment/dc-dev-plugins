#!/usr/bin/env bash
# Build the app in release mode and wrap it in build/<APP_NAME>.app. Everything app-specific is in app.env.
#   bash make-app.sh                        # build, ad-hoc signed, for this Mac
#   bash make-app.sh --open                 # build, then open it
#   bash make-app.sh --release              # sign with Developer ID, notarize, staple, DMG + zip, sign the zip for
#                                           # Sparkle, write appcast.xml, tag v<VERSION> and publish the GitHub release
#   bash make-app.sh --release --dry-run    # all of that except notarize and publish; output in build/release/
#   bash make-app.sh --release --no-publish # signed, notarized and stapled into build/release/, from any branch, with
#                                           # no tag and no GitHub release: a build to try as a new user would
# Works with Command Line Tools alone. --release needs, from the environment (RELEASING.md has the one-time setup):
#   APP_SIGN_IDENTITY     the Developer ID Application identity, e.g. "Developer ID Application: Name (TEAMID)"
#   notarization, one of: APP_NOTARY_PROFILE (a notarytool keychain profile)
#                         or APP_NOTARY_KEY + APP_NOTARY_KEY_ID + APP_NOTARY_ISSUER (App Store Connect API key)
#   SPARKLE_KEY_FILE      optional: the Sparkle private key as a file (CI). Without it sign_update reads the keychain.
# No secret is ever written into the repo, the app or the log.
# Template from the apple-dc plugin (templates/mac/make-app.sh). Fix it there first, then copy it into apps.
set -euo pipefail
OPEN=0; RELEASE=0; DRY=0; NOPUB=0
for arg in "$@"; do
  case "$arg" in
    --open) OPEN=1 ;;
    --release) RELEASE=1 ;;
    --dry-run) DRY=1 ;;
    --no-publish) NOPUB=1 ;;
    *) echo "make-app.sh: unknown option $arg" >&2; exit 2 ;;
  esac
done
[ "$DRY" = 1 ] && [ "$RELEASE" = 0 ] && { echo "make-app.sh: --dry-run only goes with --release" >&2; exit 2; }
[ "$NOPUB" = 1 ] && [ "$RELEASE" = 0 ] && { echo "make-app.sh: --no-publish only goes with --release" >&2; exit 2; }
[ "$NOPUB" = 1 ] && [ "$DRY" = 1 ] && { echo "make-app.sh: pick one of --dry-run and --no-publish" >&2; exit 2; }
[ "$OPEN" = 1 ] && [ "$RELEASE" = 1 ] && { echo "make-app.sh: --open and --release don't mix" >&2; exit 2; }
cd "$(dirname "$0")"

die() { echo "make-app.sh: $*" >&2; exit 1; }
[ -f app.env ] || die "no app.env next to make-app.sh"
# shellcheck source=/dev/null
. ./app.env
for var in APP_NAME APP_DISPLAY_NAME APP_BUNDLE_ID APP_RELEASE_REPO; do
  [ -n "${!var:-}" ] || die "app.env must set $var"
done
APP_MIN_MACOS="${APP_MIN_MACOS:-14.0}"
APP_MENU_BAR="${APP_MENU_BAR:-0}"
APP_SPARKLE_ACCOUNT="${APP_SPARKLE_ACCOUNT:-ed25519}"

APP="build/$APP_NAME.app"
REPO="$(git rev-parse --show-toplevel)"
VERSION="$(tr -d '[:space:]' < VERSION)"
TAG="v$VERSION"
REL_DIR="build/release"
# Releases, their downloads and the update feed live on APP_RELEASE_REPO. A website links
# https://github.com/<repo>/releases/latest/download/<APP_NAME>.dmg, so the asset names never change. The zip is what
# Sparkle downloads for updates. Publish nothing else on that repo: "latest" must always be the newest app.
GH_REPO="$APP_RELEASE_REPO"
FEED_URL="https://github.com/$GH_REPO/releases/latest/download/appcast.xml"

# A real release stops on a refusal. A dry run reports it and carries on, so an agent in a worktree can test the rest.
refuse() {
  if [ "$DRY" = 1 ]; then echo "make-app.sh: would refuse: $*" >&2; else die "refusing to release: $*"; fi
}
# Checks that only guard publishing: --no-publish publishes nothing, so they only warn.
refuse_publish() {
  if [ "$NOPUB" = 1 ]; then echo "make-app.sh: note (not publishing): $*" >&2; else refuse "$@"; fi
}

if [ "$RELEASE" = 1 ]; then
  [ -z "$(git -C "$REPO" status --porcelain)" ] || refuse_publish "working tree is dirty (commit first)"
  BRANCH="$(git -C "$REPO" rev-parse --abbrev-ref HEAD)"
  # CI checks out the tag's commit detached; APP_RELEASE_REF=main says it is main's head.
  [ "$BRANCH" = main ] || [ "${APP_RELEASE_REF:-}" = main ] || refuse_publish "not on main (on $BRANCH)"
  if [ -z "${APP_SIGN_IDENTITY:-}" ]; then
    # A dry run without a certificate signs ad hoc (still with the hardened runtime), so the packaging is tested.
    [ "$DRY" = 1 ] || die "APP_SIGN_IDENTITY is not set (the Developer ID Application identity)"
    APP_SIGN_IDENTITY="-"; echo "make-app.sh: dry run with no APP_SIGN_IDENTITY: signing ad hoc" >&2
  fi
  if [ "$DRY" = 0 ] && [ -z "${APP_NOTARY_PROFILE:-}" ] && [ -z "${APP_NOTARY_KEY:-}" ]; then
    die "set APP_NOTARY_PROFILE, or APP_NOTARY_KEY with APP_NOTARY_KEY_ID and APP_NOTARY_ISSUER"
  fi
  [ -s sparkle-public-key ] || refuse "sparkle-public-key is missing; run Sparkle's generate_keys --account $APP_SPARKLE_ACCOUNT and commit the public key"
  # A missing or signed-out gh would make "no release" look like the answer, so check it first.
  if [ "$NOPUB" = 0 ]; then
    { command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; } || refuse "gh is missing or not signed in (gh auth login)"
    if gh release view "$TAG" -R "$GH_REPO" >/dev/null 2>&1; then refuse "$TAG already exists as a GitHub release"; fi
    # A tag that already points elsewhere would let the binary and the tagged source disagree. CI runs on the tag
    # itself, so a tag on HEAD is fine.
    if TAGGED="$(git -C "$REPO" rev-parse -q --verify "refs/tags/$TAG^{commit}")"; then
      [ "$TAGGED" = "$(git -C "$REPO" rev-parse HEAD)" ] || refuse "$TAG already exists on another commit"
    fi
  fi
  echo "== check"
  CHECK_CMD="${APP_RELEASE_CHECK_CMD:-${APP_CHECK_CMD:-swift test}}"
  bash -c "$CHECK_CMD" || refuse "check failed ($CHECK_CMD)"
fi

swift build -c release
BIN_DIR="$(swift build -c release --show-bin-path)"

# CFBundleVersion only ever goes up: the commit count of this checkout's history. Sparkle compares it.
COMMIT="$(git -C "$REPO" rev-parse --short HEAD 2>/dev/null || echo unknown)"
BUILD="$(git -C "$REPO" rev-list --count HEAD 2>/dev/null || echo 1)"
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
MENU_BAR_KEY=""; [ "$APP_MENU_BAR" = 1 ] && MENU_BAR_KEY="  <key>LSUIElement</key><true/>"

rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources" "$APP/Contents/Frameworks"
cp "$BIN_DIR/$APP_NAME" "$APP/Contents/MacOS/$APP_NAME"
# The licence travels with every copy of the app.
[ -f "$REPO/LICENSE" ] && cp "$REPO/LICENSE" "$APP/Contents/Resources/LICENSE"
# Release notes, one file per version: What's New can read them, and the GitHub release (Sparkle's notes link) shows
# the same file.
[ -d release-notes ] && cp -R release-notes "$APP/Contents/Resources/release-notes"

# The app icon, made from icon/AppIcon.png (1024 px, already cut to the macOS tile) with sips and iconutil.
ICON_KEY=""
if [ -f icon/AppIcon.png ]; then
  ICONSET="build/AppIcon.iconset"; rm -rf "$ICONSET"; mkdir -p "$ICONSET"
  for size in 16 32 128 256 512; do
    sips -z "$size" "$size" icon/AppIcon.png --out "$ICONSET/icon_${size}x${size}.png" >/dev/null
    sips -z "$((size * 2))" "$((size * 2))" icon/AppIcon.png --out "$ICONSET/icon_${size}x${size}@2x.png" >/dev/null
  done
  iconutil -c icns -o "$APP/Contents/Resources/AppIcon.icns" "$ICONSET"
  rm -rf "$ICONSET"
  ICON_KEY="  <key>CFBundleIconFile</key><string>AppIcon</string>"
fi

# Sparkle's framework rides in Contents/Frameworks; the binary finds it through an rpath.
cp -R "$BIN_DIR/Sparkle.framework" "$APP/Contents/Frameworks/"
install_name_tool -add_rpath @executable_path/../Frameworks "$APP/Contents/MacOS/$APP_NAME" 2>/dev/null || true

# Anything else this app carries (a command line tool, bundled files): bundle-extras.sh runs here with APP, REPO and
# BIN_DIR set, before signing, so whatever it adds is signed too.
# shellcheck source=/dev/null
[ -f bundle-extras.sh ] && . ./bundle-extras.sh

cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>$APP_NAME</string>
  <key>CFBundleDisplayName</key><string>$APP_DISPLAY_NAME</string>
  <key>CFBundleIdentifier</key><string>$APP_BUNDLE_ID</string>
  <key>CFBundleExecutable</key><string>$APP_NAME</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>$VERSION</string>
  <key>CFBundleVersion</key><string>$BUILD</string>
  <key>AppBuildCommit</key><string>$COMMIT</string>
  <key>LSMinimumSystemVersion</key><string>$APP_MIN_MACOS</string>
  <key>NSHighResolutionCapable</key><true/>
$MENU_BAR_KEY
$ICON_KEY
  <key>NSHumanReadableCopyright</key><string>${APP_COPYRIGHT:-}</string>
$SPARKLE_KEYS
</dict>
</plist>
PLIST

if [ "$RELEASE" = 1 ]; then
  # Developer ID plus the hardened runtime, signed inside out as Sparkle's docs ask (no --deep). A dry run skips the
  # secure timestamp, which needs Apple's server.
  TS="--timestamp"; [ "$DRY" = 1 ] && TS="--timestamp=none"
  sign() { codesign --force --options runtime "$TS" --sign "$APP_SIGN_IDENTITY" "$@" \
    || die "codesign failed on $* (is the identity in this Mac's keychain? APP_SIGN_IDENTITY=$APP_SIGN_IDENTITY)"; }
  SP="$APP/Contents/Frameworks/Sparkle.framework/Versions/B"
  for xpc in "$SP"/XPCServices/*.xpc; do [ -e "$xpc" ] && sign --preserve-metadata=entitlements "$xpc"; done
  sign "$SP/Autoupdate"
  sign "$SP/Updater.app"
  sign "$APP/Contents/Frameworks/Sparkle.framework"
  # Mach-O binaries bundle-extras.sh added under Resources/ are signed on their own, before the app (notarization
  # rejects an unsigned one). Scripts are left alone: they ride under the app's seal.
  while IFS= read -r extra; do
    if file -b "$extra" | grep -q Mach-O; then sign "$extra"; fi
  done < <(find "$APP/Contents/Resources" -type f -perm -u+x 2>/dev/null)
  ENT=(); [ -f "$APP_NAME.entitlements" ] && ENT=(--entitlements "$APP_NAME.entitlements")
  sign ${ENT[@]+"${ENT[@]}"} "$APP"
  codesign --verify --deep --strict "$APP" || die "signature verification failed"
else
  # Ad-hoc sign so macOS will launch it on this Mac. Not for giving to anyone else.
  codesign --force --deep --sign - "$APP" >/dev/null 2>&1 || echo "warning: ad-hoc codesign failed"
fi

if [ "$RELEASE" = 1 ]; then
  rm -rf "$REL_DIR"; mkdir -p "$REL_DIR"
  ZIP="$REL_DIR/$APP_NAME.zip"
  if [ "$DRY" = 1 ]; then
    echo "== dry run: skipping notarize and staple"
  else
    echo "== notarize the app (a few minutes)"
    ditto -c -k --keepParent "$APP" "$REL_DIR/notarize.zip"
    if [ -n "${APP_NOTARY_PROFILE:-}" ]; then
      NOTARY=(--keychain-profile "$APP_NOTARY_PROFILE")
    else
      NOTARY=(--key "$APP_NOTARY_KEY" --key-id "${APP_NOTARY_KEY_ID:?}" --issuer "${APP_NOTARY_ISSUER:?}")
    fi
    xcrun notarytool submit "$REL_DIR/notarize.zip" "${NOTARY[@]}" --wait || die "notarization failed"
    rm -f "$REL_DIR/notarize.zip"
    xcrun stapler staple "$APP" || die "stapling failed"
    spctl --assess --type execute "$APP" || die "Gatekeeper rejects the notarized app"
  fi
  ditto -c -k --keepParent "$APP" "$ZIP"

  # The disk image people download: the app beside an Applications shortcut, to drag one onto the other. Sparkle keeps
  # updating from the zip; the DMG is for first installs. (An app opened straight from Downloads is translocated, and
  # Sparkle can't update a translocated copy, so the app also offers to move itself.)
  DMG="$REL_DIR/$APP_NAME.dmg"
  STAGE="$REL_DIR/dmg"; rm -rf "$STAGE"; mkdir -p "$STAGE"
  ditto "$APP" "$STAGE/$APP_NAME.app"
  ln -s /Applications "$STAGE/Applications"
  hdiutil create -volname "$APP_DISPLAY_NAME" -srcfolder "$STAGE" -fs HFS+ -format UDZO -ov "$DMG" >/dev/null \
    || die "hdiutil create failed"
  rm -rf "$STAGE"
  codesign --force "$TS" --sign "$APP_SIGN_IDENTITY" "$DMG" || die "codesign failed on $DMG"
  if [ "$DRY" = 0 ]; then
    echo "== notarize the disk image (a few minutes)"
    xcrun notarytool submit "$DMG" "${NOTARY[@]}" --wait || die "notarization of the disk image failed"
    xcrun stapler staple "$DMG" || die "stapling the disk image failed"
    spctl --assess --type open --context context:primary-signature "$DMG" || die "Gatekeeper rejects the disk image"
  fi

  SIGN_UPDATE="${SPARKLE_SIGN_UPDATE:-$(find .build/artifacts -name sign_update -type f -perm -u+x 2>/dev/null | head -n 1)}"
  { [ -n "$SIGN_UPDATE" ] && [ -x "$SIGN_UPDATE" ]; } || die "Sparkle's sign_update not found (set SPARKLE_SIGN_UPDATE, or run swift build so the package's artifacts exist)"
  KEY_ARGS=(--account "$APP_SPARKLE_ACCOUNT"); [ -n "${SPARKLE_KEY_FILE:-}" ] && KEY_ARGS=(--ed-key-file "$SPARKLE_KEY_FILE")
  # Prints: sparkle:edSignature="..." length="..."
  if ! SIG="$("$SIGN_UPDATE" "${KEY_ARGS[@]}" "$ZIP")"; then
    refuse "sign_update failed (is the Sparkle key for account $APP_SPARKLE_ACCOUNT in this Mac's keychain, or SPARKLE_KEY_FILE set?)"
    SIG='sparkle:edSignature="DRY-RUN-UNSIGNED" length="0"'
  fi
  case "$SIG" in *sparkle:edSignature=*) ;; *) die "sign_update gave no signature" ;; esac
  SIG="$(printf '%s' "$SIG" | tr -d '\n')"

  # The feed holds only the newest version: Sparkle needs nothing more.
  cat > "$REL_DIR/appcast.xml" <<APPCAST
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:sparkle="http://www.andymatuschak.org/xml-namespaces/sparkle">
  <channel>
    <title>$APP_DISPLAY_NAME</title>
    <item>
      <title>$APP_DISPLAY_NAME $VERSION</title>
      <link>https://github.com/$GH_REPO/releases/tag/$TAG</link>
      <sparkle:releaseNotesLink>https://github.com/$GH_REPO/releases/tag/$TAG</sparkle:releaseNotesLink>
      <pubDate>$(LC_ALL=C date -u "+%a, %d %b %Y %H:%M:%S +0000")</pubDate>
      <sparkle:version>$BUILD</sparkle:version>
      <sparkle:shortVersionString>$VERSION</sparkle:shortVersionString>
      <sparkle:minimumSystemVersion>$APP_MIN_MACOS</sparkle:minimumSystemVersion>
      <enclosure url="https://github.com/$GH_REPO/releases/download/$TAG/$APP_NAME.zip" type="application/octet-stream" $SIG/>
    </item>
  </channel>
</rss>
APPCAST
  if [ "$DRY" = 1 ]; then
    echo "Dry run done: $(pwd)/$DMG, $(pwd)/$ZIP and $(pwd)/$REL_DIR/appcast.xml (not notarized, not published)"
    exit 0
  fi
  if [ "$NOPUB" = 1 ]; then
    echo "Built $(pwd)/$DMG and $(pwd)/$ZIP: signed, notarized and stapled (not tagged, not published)"
    exit 0
  fi
  echo "== publish $TAG"
  SOURCE="$(git -C "$REPO" rev-parse HEAD)"
  if ! git -C "$REPO" rev-parse -q --verify "refs/tags/$TAG" >/dev/null; then
    git -C "$REPO" tag "$TAG" "$SOURCE" && git -C "$REPO" push origin "refs/tags/$TAG" || die "could not tag $SOURCE as $TAG"
  fi
  NOTES="$APP_DISPLAY_NAME $VERSION (build $BUILD, source $SOURCE)."
  # The release notes file, without its front matter.
  [ -f "release-notes/$VERSION.md" ] && NOTES="$(awk 'NR==1 && /^---$/ {fm=1; next} fm && /^---$/ {fm=0; next} !fm' "release-notes/$VERSION.md")"
  gh release create "$TAG" "$DMG" "$ZIP" "$REL_DIR/appcast.xml" -R "$GH_REPO" --verify-tag \
    --title "$APP_DISPLAY_NAME $VERSION" --notes "$NOTES" || die "gh release create failed"
  echo "Published $TAG: https://github.com/$GH_REPO/releases/tag/$TAG"
  exit 0
fi

ABS="$(cd "$(dirname "$APP")" && pwd)/$(basename "$APP")"
echo "Built $ABS"
[ "$OPEN" = 1 ] && open "$ABS"
exit 0
