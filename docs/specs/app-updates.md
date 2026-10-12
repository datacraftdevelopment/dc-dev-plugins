# Spec: the Runway app updates itself and keeps every Mac on the same Runway

Tracker entry: #66 (tickets #67-#71, its sub-issues).

## Problem

Joe runs Runway on two Macs: his personal Mac and his work Mac. Each runs its own
loops on its own repos. They never share a repo, so each repo's `park_authority`
names the Mac that runs it. Both Macs should always have the same Runway, the
same app features and the same engine, whichever Mac a change was made on
(Joe, 2026-10-12: "keep feature parity between the two of them").

Today an update is three manual steps per Mac: `git pull` the dc-dev-plugins
checkout the loops run the engine from, `/plugin marketplace update dc-dev-plugins`
(plus a session restart), and `bash factory/app/make-app.sh --install` when the
app changed. A Mac that skips a step ends up quietly behind. A new Mac starts from
nothing.

## Goal

This repo is the one update path. A change merges to `main`. If it touches the
app, Joe cuts a release. From there, every Mac's app updates itself and brings the
engine checkout and the pm plugin up to date with it. The app always shows what
this Mac is running and says when it's behind.

## Rules

- **One source.** The engine runs from the dc-dev-plugins checkout named in the
  app's Scripts setting, as today. App builds come only from this repo's GitHub
  Releases. Nothing is copied between Macs by hand.
- **Updater.** Sparkle 2, added as a Swift package and pinned exactly, like
  SwiftTerm. (Joe uses an updater in another of his apps. If it isn't Sparkle,
  this line changes before ticket 2 runs.) Updates are checked automatically once a
  day, and on demand from a "Check for Updates…" menu item. Each update archive is
  EdDSA-signed. The public key is committed in `factory/app/sparkle-public-key`
  (it isn't secret). The private key never enters the repo or a log, and stays in
  Joe's keychain on his personal Mac. A build without a public key has the updater
  turned off and says so in the menu. It never crashes, and it never accepts
  unsigned updates.
- **Feed.** The appcast is a release asset, read from
  `https://github.com/datacraftdevelopment/dc-dev-plugins/releases/latest/download/appcast.xml`.
  App releases are tagged `runway-app-v<version>`. No other kind of release is
  published on this repo; if one ever is, the feed URL moves to a fixed tag first.
- **Version.** `factory/app/VERSION` holds the marketing version, and
  `make-app.sh` writes it into `CFBundleShortVersionString`. `CFBundleVersion` is a
  build number that only ever goes up (the commit count on `main`).
- **Releases are Joe's.** `make-app.sh --release` builds, signs with Developer ID
  and the hardened runtime, notarizes and staples, zips, signs the zip for Sparkle,
  writes `appcast.xml` and publishes the GitHub release. It refuses to run if the
  working tree is dirty, if it isn't on `main`, if `VERSION` already has a tag, or
  if the check fails. Publishing is public and can't be quietly undone, so Runway
  never runs it. `--release --dry-run` does everything except notarize and publish,
  so an agent can test it.
- **Bring the rest along.** When the app starts and finds its bundle version is
  newer than the last one it recorded, and whenever Joe clicks "Update Runway",
  it does the following in order, stopping at the first failure and showing that
  step's output:
  1. Wait while any loop is mid-tick, meaning a heartbeat in an active phase.
     Pull only between ticks, and retry on the next status refresh.
  2. `git -C <checkout> pull --ff-only origin main`, but only when that
     checkout is on `main` and clean. Otherwise skip, and say why ("checkout is
     on a branch", "uncommitted changes"). Never stash, reset or switch branches.
  3. `claude plugin marketplace update dc-dev-plugins`, then
     `claude plugin update pm@dc-dev-plugins`, run through a login shell, the
     same way the setup checks run them.
  4. Report the result: "Updated: engine <short sha>, pm <version>. Restart open
     Claude sessions to pick up the new skills."
  It never touches any repo other than the engine checkout, and never loads or
  unloads a LaunchAgent. The loops pick up the new engine on their next tick
  because they run it from the checkout.
- **Parity you can see.** The app's About/Status line shows the app version, the
  engine checkout's short SHA and branch, and the installed pm version. It shows a
  "Behind" badge when any of these is behind: the app is older than the feed's
  latest, the checkout is behind `origin/main` (checked with a `git fetch` at most
  hourly), or the installed pm is older than `pm/.claude-plugin/plugin.json` in
  the checkout. The badge's action is "Update Runway".
- **A new Mac.** The existing "Set up a loop…" sheet (`Setup.swift`) gains these
  checks: pm installed from dc-dev-plugins, Matt's skills installed, `gh` signed
  in to an account that can read the repo being set up (`gh api repos/<owner/name>`),
  and Ringer and Codex as optional items. On Linear, the key check uses the
  repo's `keychain_service` from `runway.json` instead of a hard-coded
  `runway-linear`. When it sets up a new repo, the sheet writes this root's
  `park_authority` into that repo's `runway.json` and commits it, but only when
  the repo has none yet. A repo that already names a different owner stops the
  flow, the message points to `pm/runway/park-ownership.md`, and the sheet never
  overwrites an existing owner.
- **Public repo.** Nothing about the work Mac's projects goes into this repo.
  Engine and app fixes are fine. Release notes describe Runway changes only.

## Out of scope

- Runway publishing releases by itself, or a release step inside `finish`.
- Moving a loop between Macs. That's the deliberate handoff in
  `park-ownership.md`, and nothing here automates it.
- Updating Ringer or Codex. They're listed, not managed.
- Non-Mac machines.

## Tickets

1. #67 **Signing and keys (Joe only, no Runway label).** Developer ID Application
   certificate on the personal Mac, a `notarytool` keychain profile, and Sparkle's
   `generate_keys`, with the public key committed to `factory/app/sparkle-public-key`.
   Gates ticket 4's first real release, not its build.
2. #68 **Sparkle in the app** (`ready-for-agent`). Package dependency, updater
   controller, "Check for Updates…", feed URL and public key in `Info.plist` via
   `make-app.sh`, `VERSION` file, build number, and the updater turned off when
   there's no key.
3. #69 **Update Runway and the parity line** (`ready-for-agent`, `harness:opus`). The
   bring-the-rest-along steps, the version-change trigger, the menu item, the
   status line and the Behind badge. Command builders and state logic live in
   `RunwayCore` with unit tests. The views only display them.
4. #70 **Release command** (`ready-for-agent`). `make-app.sh --release` and
   `--dry-run` as described above. Acceptance runs the dry run only.
5. #71 **Setup sheet for a new Mac** (`ready-for-agent`, `harness:opus`, blocked by 3).
   The new checks, the per-repo keychain item, and writing `park_authority` only
   when none is set.

Order: 2 → 3 → 5, and 2 → 4. Ticket 1 can happen any time before the first
real release.
