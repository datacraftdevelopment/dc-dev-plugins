---
name: app-store
description: Ship an iOS app (or a sandboxed Mac app) through App Store Connect - the one-time app record and API key, archive and upload with ship.sh, TestFlight testers, then the store listing, privacy answers and review submission. Use when the user says "TestFlight", "upload a build", "submit to the App Store", "App Store Connect", "put it on the store", or an iOS app is ready for anyone but the developer to run.
---

# App Store and TestFlight

Read the `app-support` notebook first: the app's section (App Store Connect name, which API key) and every lesson
tagged with an iOS or App Store app. **This path is new**: the first apps through it write its lessons. Say so when a
step below fails in a way it doesn't describe, fix forward, and record what worked.

Which actions are whose:

| Step | Who | Undoable? |
| --- | --- | --- |
| Create the app record, accept agreements, fill the listing, submit for review, release | The user, in App Store Connect (agents draft the words) | Review submissions and releases are public |
| Archive, upload to TestFlight | `ship.sh --testflight`, with the user's go per upload | A build can be expired, not deleted |
| Internal testers | The user or an agent with their go | Yes |

## One-time setup, per app

1. **Bundle ID and app record.** In App Store Connect, My Apps > + > New App, with the bundle ID from `project.yml`
   (register it at developer.apple.com > Identifiers first if it isn't offered). The name must be unique on the
   store. The record can't be made from the command line.
2. **An API key that can upload and sign.** `ship.sh` uses automatic signing with
   `-allowProvisioningUpdates` and an App Store Connect API key, so Xcode creates the distribution certificate and
   profile itself. A **Developer** role key notarizes but may not be allowed to manage distribution signing; if the
   archive or export fails on a permissions or provisioning error, make a separate key with **App Manager** role for
   uploads (Users and Access > Integrations > Team Keys) rather than raising the notary key. Note which key is which
   in the notebook; the `.p8` lives in the user's password manager and `~/.appstoreconnect/private_keys/`, never in a
   repo.
3. **Icon** (`app-icon`): opaque, 1024 px. `ship.sh` refuses to archive without one.
4. **Privacy manifest**: the template's `Resources/PrivacyInfo.xcprivacy` declares UserDefaults (CA92.1) and no
   tracking or collected data. Keep it true as the app grows: an upload that uses a "required reason" API without
   declaring it gets flagged or rejected.

## Upload a build

```bash
cd _ios && bash ship.sh                       # tests on a simulator first; must pass
ASC_KEY_PATH=<.p8> ASC_KEY_ID=<id> ASC_ISSUER=<issuer> bash ship.sh --archive      # signed .ipa in build/, no upload
ASC_KEY_PATH=<.p8> ASC_KEY_ID=<id> ASC_ISSUER=<issuer> bash ship.sh --testflight   # from a clean main: upload
```

The version is `VERSION`; the build number is the commit count, so each upload is higher than the last (App Store
Connect refuses a repeat). `ITSAppUsesNonExemptEncryption: false` in `project.yml` skips the export compliance
question on each build; change it if the app adds its own encryption.

After upload, processing takes minutes to an hour; the build then shows under TestFlight. **Internal testers** (people
on the team) can install it at once; **external testers** need a short Beta App Review first, then a public link or
invitations.

## Submit to the App Store

Draft everything the listing needs in `<app folder>/store/` (committed, plain text) so the user can paste it into App
Store Connect:

- name, subtitle (30 characters), promotional text, description, keywords (100 characters), support URL, privacy
  policy URL (required);
- screenshots for the largest iPhone size App Store Connect currently asks for (take them on that simulator), and
  iPad if the app supports it;
- the privacy questionnaire's answers (must match `PrivacyInfo.xcprivacy`), age rating answers, review notes (how to
  reach every feature, a demo login if any).

Then the user picks the build, submits for review, and chooses manual or automatic release. Rejections come back in
App Store Connect's Resolution Center; record each reason in `lessons.md`, because they repeat.

## The Mac App Store

A Mac app can go through the same pipeline, but not from the Developer ID template: the store requires the App
Sandbox, and it updates apps itself. So a Mac App Store app needs an Xcode project (XcodeGen, `platform: macOS`) with
the `com.apple.security.app-sandbox` entitlement, no Sparkle and no move-to-Applications offer, and the same
`ship.sh`-style archive and upload with `method: app-store-connect`. Check first that the app can live sandboxed:
anything that runs other programs, reads arbitrary folders or controls other apps usually can't, and stays on
Developer ID (`mac-release`). Nothing is templated for this yet; build it from the first app that needs it, then
promote what worked into `templates/`.
