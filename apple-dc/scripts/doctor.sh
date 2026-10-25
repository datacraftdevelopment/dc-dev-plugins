#!/usr/bin/env bash
# What this Mac can sign and ship with, checked for real rather than remembered. Prints one line per check; never
# prints a secret. Exit code 1 if anything a release would need is missing.
#   bash doctor.sh                                   # tools and signing identities
#   bash doctor.sh --notary NAME [--notary NAME…]    # also try each notarytool profile against Apple
#   bash doctor.sh --sparkle ACCOUNT [--sparkle-bin DIR]  # also look for that app's Sparkle key in the keychain
set -uo pipefail
NOTARY=(); SPARKLE=(); SPARKLE_BIN=""
while [ $# -gt 0 ]; do
  case "$1" in
    --notary) NOTARY+=("$2"); shift 2 ;;
    --sparkle) SPARKLE+=("$2"); shift 2 ;;
    --sparkle-bin) SPARKLE_BIN="$2"; shift 2 ;;
    *) echo "doctor.sh: unknown option $1" >&2; exit 2 ;;
  esac
done
BAD=0
ok() { echo "ok      $*"; }
no() { echo "MISSING $*"; BAD=1; }
note() { echo "note    $*"; }

[ "$(uname)" = Darwin ] || { echo "doctor.sh: run this on the Mac that signs (this is $(uname))" >&2; exit 2; }
if DEV="$(xcode-select -p 2>/dev/null)"; then ok "developer tools at $DEV"; else no "developer tools (xcode-select --install)"; fi
if xcodebuild -version >/dev/null 2>&1; then ok "$(xcodebuild -version | head -1) (iOS and App Store builds need full Xcode)"
else note "no full Xcode: Mac apps build with Command Line Tools, iOS apps and App Store uploads need Xcode"; fi
if command -v xcodegen >/dev/null 2>&1; then ok "xcodegen $(xcodegen --version 2>/dev/null | awk '{print $NF}')"
else note "xcodegen missing (brew install xcodegen), needed for iOS apps"; fi
if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then ok "gh signed in"; else no "gh signed in (gh auth login), needed to publish Mac releases"; fi
if python3 -c 'import PIL' 2>/dev/null; then ok "Pillow for make-icons.py"; else note "Pillow missing (pip3 install pillow), needed for make-icons.py"; fi

IDS="$(security find-identity -v -p codesigning 2>/dev/null)"
for kind in "Developer ID Application" "Apple Distribution" "Apple Development"; do
  name="$(printf '%s\n' "$IDS" | sed -n "s/.*\"\($kind: .*\)\"/\1/p" | head -1)"
  if [ -n "$name" ]; then ok "identity: $name"
  elif [ "$kind" = "Developer ID Application" ]; then no "identity: $kind (Xcode > Settings > Accounts > Manage Certificates)"
  else note "no $kind identity (Xcode makes one on the first App Store or device build)"; fi
done

for profile in ${NOTARY[@]+"${NOTARY[@]}"}; do
  if xcrun notarytool history --keychain-profile "$profile" >/dev/null 2>&1; then ok "notary profile $profile works"
  else no "notary profile $profile fails (store it again: xcrun notarytool store-credentials $profile --key … --key-id … --issuer …)"; fi
done

if [ ${#SPARKLE[@]} -gt 0 ]; then
  GEN="${SPARKLE_BIN:+$SPARKLE_BIN/generate_keys}"
  [ -n "$GEN" ] || GEN="$(find . -path '*sparkle*' -name generate_keys -type f -perm -u+x 2>/dev/null | head -1)"
  if [ -z "$GEN" ] || [ ! -x "$GEN" ]; then
    no "Sparkle's generate_keys (swift build in a Sparkle app first, or pass --sparkle-bin)"
  else
    for account in "${SPARKLE[@]}"; do
      if pub="$("$GEN" --account "$account" -p 2>/dev/null)" && [ -n "$pub" ]; then ok "Sparkle key '$account', public key $pub"
      else no "Sparkle key '$account' is not in this Mac's keychain"; fi
    done
  fi
fi
exit "$BAD"
