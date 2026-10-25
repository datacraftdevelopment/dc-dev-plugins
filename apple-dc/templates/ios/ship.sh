#!/usr/bin/env bash
# Build, test and ship the iOS app. The Xcode project is generated from project.yml every run.
#   bash ship.sh                     # generate, build and run the tests on an iPhone simulator
#   bash ship.sh --archive           # also archive and export a signed .ipa into build/ (no upload)
#   bash ship.sh --testflight        # archive and upload to App Store Connect, where it lands in TestFlight
# Needs Xcode and XcodeGen (brew install xcodegen). --archive and --testflight sign with automatic signing and an
# App Store Connect API key, from the environment (no secret is ever written into the repo or the log):
#   ASC_KEY_PATH   the .p8 file      ASC_KEY_ID   its key ID      ASC_ISSUER   the issuer ID
# Template from the apple-dc plugin (templates/ios/ship.sh). Fix it there first, then copy it into apps.
set -euo pipefail
MODE=test
case "${1:-}" in
  "") ;;
  --archive) MODE=archive ;;
  --testflight) MODE=testflight ;;
  *) echo "ship.sh: unknown option $1" >&2; exit 2 ;;
esac
cd "$(dirname "$0")"
die() { echo "ship.sh: $*" >&2; exit 1; }

APP="$(awk '/^name:/ {print $2; exit}' project.yml)"
[ -n "$APP" ] || die "project.yml has no name:"
REPO="$(git rev-parse --show-toplevel)"
VERSION="$(tr -d '[:space:]' < VERSION)"
# The build number only ever goes up: the commit count of this checkout. App Store Connect refuses a repeat.
BUILD="$(git -C "$REPO" rev-list --count HEAD 2>/dev/null || echo 1)"
VERSIONS=(MARKETING_VERSION="$VERSION" CURRENT_PROJECT_VERSION="$BUILD")

command -v xcodegen >/dev/null 2>&1 || die "xcodegen is missing (brew install xcodegen)"
xcodegen generate --quiet

if [ "$MODE" = testflight ]; then
  [ -z "$(git -C "$REPO" status --porcelain)" ] || die "working tree is dirty (commit first)"
  [ "$(git -C "$REPO" rev-parse --abbrev-ref HEAD)" = main ] || die "not on main"
fi

if [ "$MODE" != test ]; then
  for var in ASC_KEY_PATH ASC_KEY_ID ASC_ISSUER; do [ -n "${!var:-}" ] || die "$var is not set"; done
  [ -f "$ASC_KEY_PATH" ] || die "no key file at ASC_KEY_PATH"
  # App Store Connect rejects a build with no icon, so stop here rather than after a ten-minute archive.
  ls Resources/Assets.xcassets/AppIcon.appiconset/*.png >/dev/null 2>&1 \
    || die "no app icon yet (the app-icon skill makes Resources/Assets.xcassets/AppIcon.appiconset/AppIcon.png)"
fi

echo "== test on a simulator"
SIM="$(xcrun simctl list devices available -j | python3 -c '
import json, sys
devices = json.load(sys.stdin)["devices"]
phones = [d for runtime, ds in sorted(devices.items()) if "iOS" in runtime for d in ds if d["name"].startswith("iPhone")]
print(phones[-1]["udid"] if phones else "")')"
[ -n "$SIM" ] || die "no iPhone simulator installed (Xcode > Settings > Components)"
xcodebuild test -project "$APP.xcodeproj" -scheme "$APP" -destination "id=$SIM" -quiet "${VERSIONS[@]}" \
  || die "tests failed"
[ "$MODE" = test ] && { echo "Tests passed ($APP $VERSION, build $BUILD)"; exit 0; }

AUTH=(-allowProvisioningUpdates -authenticationKeyPath "$ASC_KEY_PATH"
      -authenticationKeyID "$ASC_KEY_ID" -authenticationKeyIssuerID "$ASC_ISSUER")
ARCHIVE="build/$APP.xcarchive"
rm -rf build; mkdir -p build
echo "== archive $APP $VERSION ($BUILD)"
xcodebuild archive -project "$APP.xcodeproj" -scheme "$APP" -destination 'generic/platform=iOS' \
  -archivePath "$ARCHIVE" -quiet "${AUTH[@]}" "${VERSIONS[@]}" || die "archive failed"

OPTIONS="ExportOptions.plist"
if [ "$MODE" = archive ]; then
  # The same options, but exported to build/ instead of uploaded.
  OPTIONS="build/ExportOptions.plist"
  sed 's#<string>upload</string>#<string>export</string>#' ExportOptions.plist > "$OPTIONS"
fi
echo "== export ($MODE)"
xcodebuild -exportArchive -archivePath "$ARCHIVE" -exportOptionsPlist "$OPTIONS" -exportPath build/export \
  "${AUTH[@]}" || die "export failed"

if [ "$MODE" = archive ]; then
  echo "Exported $(pwd)/build/export (not uploaded)"
else
  echo "Uploaded $APP $VERSION ($BUILD). It shows in App Store Connect > TestFlight once processing finishes."
fi
