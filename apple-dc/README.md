# apple-dc

Build, sign and ship Mac and iOS apps, and get better at it with every app.

| Skill | Does |
| --- | --- |
| `app-support` | The private notebook every other skill reads first and writes to after: `apps.md`, `machine.md`, `lessons.md`. Promotes generic lessons back into this plugin. |
| `new-apple-app` | Scaffolds a Mac app (SwiftPM, menu bar or window, Sparkle, move-to-Applications, `make-app.sh`, CI dry run) or an iOS app (XcodeGen, simulator tests, `ship.sh`). |
| `app-icon` | Drafts icon options through Codex (via Ringer) or takes the user's artwork, then cuts the macOS tile, the iOS asset-catalog icon and favicons. |
| `mac-release` | Developer ID, hardened runtime, notarization with an API key, DMG + Sparkle zip + appcast, GitHub release, a check from outside. |
| `app-store` | App Store Connect: app record, API key, TestFlight upload with `ship.sh`, listing and review; notes for the Mac App Store. |

| Script | Does |
| --- | --- |
| `scripts/new-app.py` | Copies `templates/mac` or `templates/ios` into a repo with the app's names filled in |
| `scripts/make-icons.py` | One square artwork to the macOS tile, the iOS icon and web icons (needs `pip3 install pillow`) |
| `scripts/doctor.sh` | What this Mac can sign and ship with, checked for real (identities, notary profiles, Sparkle keys, tools) |

The templates are the source of truth for each app's `make-app.sh` and `ship.sh`: fix a script here first, then copy
it into the apps.

## What it assumes

A Mac with Xcode (Command Line Tools are enough for Mac apps; iOS and App Store work needs full Xcode), `gh` signed in
for Mac releases, `brew install xcodegen` for iOS, and an Apple Developer account. Codex icon drafts go through Ringer.
Nothing personal is in this plugin: team IDs, profile names and which app uses which key live in the user's
app-support folder, found through `~/.apple-dc.json`.
