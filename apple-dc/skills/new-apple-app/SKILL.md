---
name: new-apple-app
description: Scaffold a new Mac or iOS app in a repo, ready to build, test and ship from day one. Mac (SwiftPM, menu bar or window app, Sparkle updates, move-to-Applications, make-app.sh, CI dry run) or iOS (XcodeGen project, simulator tests, ship.sh for TestFlight). Use when the user says "new Mac app", "new iOS app", "start an app", "scaffold an app", or wants an existing idea turned into a buildable app.
---

# New Apple app

Read the `app-support` notebook first (that skill says how): the stack and naming of earlier apps, this Mac's team
ID, and any lesson about scaffolding.

## Settle these first (ask only what the request didn't say)

| Choice | Default | Why it matters |
| --- | --- | --- |
| Platform | from the request | Mac and iOS use different templates; an app for both is two folders, sharing a Swift package later if needed |
| Name (Swift type, no spaces) and display name | | The name becomes the executable and the release asset names: fixed after the first release |
| Bundle ID | the notebook's convention for earlier apps | Locked for good after the first release or App Store record |
| Mac: menu bar or window | menu bar | `--window` for a Dock app with a window |
| Mac: where releases go | the app's own GitHub repo | Its "latest" release must only ever be this app |
| Mac: Developer ID or Mac App Store | Developer ID | The App Store needs the sandbox and an Xcode project, not this template (see `app-store`) |
| iOS: team ID | from `machine.md` | Written into `project.yml` and `ExportOptions.plist` |
| Folder | `_mac` or `_ios` | One underscore folder per code surface, as pm-sp lays out a project |

If the repo has no `_pm/` or `CLAUDE.md` yet and pm-sp is installed, run its `scaffold` first; this skill adds the
app, not the project around it.

## Scaffold

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/new-app.py mac --repo . --name <Name> --display "<Display>" \
  --bundle-id <bundle.id> --release-repo <owner/repo> --owner "<copyright holder>" [--window]
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/new-app.py ios --repo . --name <Name> --display "<Display>" \
  --bundle-id <bundle.id> --team <TEAMID>
```

It refuses to write over an existing folder and prints every file it wrote.

**Mac** gets: `Package.swift` (Sparkle pinned exactly), the app target with "Check for Updates…" and the
move-to-Applications offer, a `<Name>Core` library with its tests, `app.env` (everything app-specific),
`make-app.sh`, `RELEASING.md`, `VERSION`, `release-notes/`, and `.github/workflows/<folder>.yml` (tests plus a release
dry run on every PR). Anything else the app must carry inside its bundle goes in a `bundle-extras.sh` next to
`make-app.sh` (it runs with `APP`, `REPO` and `BIN_DIR` set, before signing).

**iOS** gets: `project.yml` (XcodeGen; the `.xcodeproj` is generated and gitignored), the app and test targets, an
asset catalog waiting for its icon, `ExportOptions.plist`, `ship.sh`, `VERSION`, `release-notes/`.

## Prove it builds, then record it

- Mac: `cd <folder> && swift test && bash make-app.sh --open`. Then `bash make-app.sh --release --dry-run`: it signs
  ad hoc and builds the DMG, zip and appcast without secrets.
- iOS: `bash <folder>/ship.sh` (needs Xcode and `brew install xcodegen`): generates the project and runs the tests on
  a simulator.

These need macOS. From a cloud session, run them on the user's Mac (Remote Control), or say they are still to run.

Then add the app's section to `apps.md`, and commit the scaffold on a branch. Next steps, offered rather than done:
an icon (`app-icon`), the one-time release setup (`mac-release` or `app-store`).

The templates are the source of truth: a fix found in one app's `make-app.sh` or `ship.sh` goes back into
`${CLAUDE_PLUGIN_ROOT}/templates/` by PR, then into the other apps.
