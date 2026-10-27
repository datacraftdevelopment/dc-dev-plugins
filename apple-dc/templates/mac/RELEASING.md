# Releasing __DISPLAY__

A release is a Developer ID-signed, notarized `__APP__.dmg` (first installs), `__APP__.zip` (updates) and an
`appcast.xml`, published as the GitHub release `v<VERSION>` on `__REPO__`. Every installed copy checks the feed once a
day (and on "Check for Updates…"), and Sparkle installs the new version after checking the zip's EdDSA signature
against the public key built into the app, and the new app's Developer ID.

| What | Where |
| --- | --- |
| Download (website link, always the newest) | `https://github.com/__REPO__/releases/latest/download/__APP__.dmg` |
| Update feed (built into the app) | `https://github.com/__REPO__/releases/latest/download/appcast.xml` |

Only app releases are published on that repo, because "latest" must always be the newest app. Publishing is public
and reaches every installed copy, and it can't be quietly taken back: fix forward with a higher version.

## Cutting a release

1. On a branch, bump `VERSION` and write `release-notes/<VERSION>.md` (a few plain `- ` lines; it becomes the release
   page and so Sparkle's update window). Merge to `main`.
2. On the Mac that holds the keys, on a clean `main`:
   `APP_SIGN_IDENTITY="Developer ID Application: …" APP_NOTARY_PROFILE=<profile> bash make-app.sh --release`

`make-app.sh --release` refuses on a dirty tree, off `main`, when `v<VERSION>` exists, or when the check fails.
`--release --dry-run` does everything except notarize and publish, needs no secrets, and runs in CI on every PR.
`--release --no-publish` gives a signed, notarized DMG and zip from any branch, to try as a new user would: download
it on a clean account, open the DMG, drag the app to Applications, and run `spctl -a -vvv -t exec` on it (it must
say `Notarized Developer ID`).

## One-time setup

Nothing below ever goes into the repo. The only key that is committed is Sparkle's **public** key.

1. **Developer ID Application certificate** in the login keychain (Xcode > Settings > Accounts > Manage
   Certificates). `security find-identity -v -p codesigning` shows its full name: that is `APP_SIGN_IDENTITY`.
2. **Notarization:** an App Store Connect API key (Users and Access > Integrations > Team Keys, role Developer),
   stored once as a notarytool profile:
   `xcrun notarytool store-credentials <profile> --key <AuthKey.p8> --key-id <KEYID> --issuer <ISSUER>`.
   Don't use an app-specific password: an Apple ID password reset revokes every one of them.
3. **Sparkle key, one per app:** `swift build` (fetches Sparkle), then
   `.build/artifacts/sparkle/Sparkle/bin/generate_keys --account __SPARKLE_ACCOUNT__`. The private key stays in this
   Mac's keychain; put the printed public key in `sparkle-public-key` and commit it. Back the private key up
   (`generate_keys --account __SPARKLE_ACCOUNT__ -x <file>`, into the password manager, then delete the file):
   **losing it means installed copies can never update again.**

## Install and updates

The DMG shows the app beside an Applications shortcut. Opened from anywhere else (Downloads, the disk image itself),
the app offers to move itself into Applications and reopen, because Sparkle can't update a copy macOS has
translocated or one on a read-only disk image. `NO_MOVE_TO_APPLICATIONS=1` skips the offer and `NO_UPDATES=1` turns
the updater off for a run; developer builds in `build/` never ask.
