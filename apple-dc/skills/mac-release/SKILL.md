---
name: mac-release
description: Set up and cut a signed, notarized, self-updating release of a Mac app outside the App Store - Developer ID and the hardened runtime, notarization with an App Store Connect API key, a drag-to-Applications DMG, a Sparkle-signed zip and appcast, a GitHub release, and a check from outside. Use when the user says "release", "ship a new version", "sign and notarize", "set up updates", "make a DMG", or a Mac app needs its first release. For the Mac App Store, use app-store instead.
---

# Mac release (Developer ID + notarization + DMG + Sparkle)

Read the `app-support` notebook first: the app's section (release repo, notary profile, Sparkle account, last
version) and this Mac's section. Then refresh the Mac's facts for real:

```bash
bash ${CLAUDE_PLUGIN_ROOT}/scripts/doctor.sh --notary <the app's profile> --sparkle <the app's Sparkle account>
```

A `MISSING` line is the first thing to fix; say which, and how (the fixes are below).

The app's own `make-app.sh` does the work; it came from `${CLAUDE_PLUGIN_ROOT}/templates/mac/` (an app scaffolded by
`new-apple-app` has it). An older app with its own scripts: copy in `make-app.sh` and write an `app.env`, keeping
the app's existing bundle ID, executable name and Sparkle key, so installed copies still update.

## One-time setup, per Mac and per app

Nothing below ever goes into a repo; only a Sparkle **public** key is committed. The app's `RELEASING.md` has the
same steps with its own names.

1. **Developer ID Application certificate** (per Mac; lasts five years): Xcode > Settings > Accounts > Manage
   Certificates. Another Mac gets it as an exported `.p12`.
2. **Notarization with an App Store Connect API key**, stored as a notarytool profile:
   `xcrun notarytool store-credentials <profile> --key <AuthKey.p8> --key-id <KEYID> --issuer <ISSUER>`.
   One key and one profile can serve every app. **Never app-specific passwords**: resetting the Apple ID password
   revokes all of them, and every profile built on one breaks at once.
3. **A Sparkle key per app** (per app, on the Mac that releases it): `swift build`, then
   `.build/artifacts/sparkle/Sparkle/bin/generate_keys --account <account>` (the account is `APP_SPARKLE_ACCOUNT` in
   `app.env`). Commit the printed public key as `sparkle-public-key`. Have the user back up the private key
   (`generate_keys --account <account> -x <file>` into their password manager, then delete the file): losing it means
   installed copies can never update again.
4. **The release repo**: the app's own public GitHub repo, with nothing but app releases on it, so
   `releases/latest/download/<App>.dmg` is a stable website link.

Record each step's outcome in the notebook (profile name, Sparkle account, where backups live).

## Try it as a new user would

```bash
APP_SIGN_IDENTITY="Developer ID Application: …" APP_NOTARY_PROFILE=<profile> bash make-app.sh --release --no-publish
```

From any branch: signed, notarized and stapled `build/release/<App>.dmg` and `.zip`, no tag, no release. Check it the
way a stranger's Mac will: `spctl -a -vvv -t exec build/<App>.app` must say `Notarized Developer ID`, and
`spctl -a -vvv -t open --context context:primary-signature build/release/<App>.dmg` must accept the disk image.

## Release

Publishing is public, reaches every installed copy within a day, and can't be quietly taken back: **it needs the
user's go each time**, in their own words. Auto mode stops an agent from publishing anyway; when it does, hand the
user the one command rather than looking for a way round it.

1. On a branch: bump `VERSION`, write `release-notes/<VERSION>.md`, merge to `main`.
2. On the Mac that holds the keys, on a clean, pulled `main`:
   `APP_SIGN_IDENTITY="Developer ID Application: …" APP_NOTARY_PROFILE=<profile> bash make-app.sh --release`
3. Check from outside: download the DMG from the release's `latest/download` link with curl, mount it, and run
   `spctl` on the app inside, as above. Then update the app's "last shipped" line in the notebook.

`make-app.sh --release` refuses on a dirty tree, off `main`, when the version's tag or release already exists, or
when the app's check fails. A failed release changes nothing public until `gh release create` runs.

## Why it is built this way

- **Signed inside out, no `--deep`:** Sparkle's XPC services, Autoupdate and Updater.app, then the framework, then
  the app, all with the hardened runtime and a secure timestamp. Notarization rejects anything unsigned inside.
- **DMG for first installs, zip for updates.** An app opened straight from Downloads is translocated (run from a
  random read-only path), and Sparkle can't replace a translocated copy or one on a disk image. So the DMG shows the
  app beside an Applications shortcut, and the app offers to move itself to Applications when run from anywhere
  else.
- **The build number is the commit count,** so it only ever goes up; Sparkle compares it, not the version string.
- **The feed holds only the newest version** and lives at `releases/latest/download/appcast.xml`.

## Electron apps

electron-builder signs and notarizes on its own: set `mac.hardenedRuntime: true`, `mac.notarize: true`, and give it
the same API key through `APPLE_API_KEY`, `APPLE_API_KEY_ID` and `APPLE_API_ISSUER`. Updates there are
electron-updater's, not Sparkle's. The DMG and translocation advice above still holds. Record what worked in the
notebook; this section is thinner than the Swift path because no Electron app has shipped through it yet.
