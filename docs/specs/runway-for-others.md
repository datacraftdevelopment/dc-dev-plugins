# Spec: Runway someone else can install, set up and keep running

Status: long-term direction, not current work. No tickets. Joe (2026-10-12):
"This is the long-term vision ... Now it's just me running it on two Macs and
getting it working." Current work is `app-updates.md` and `app-chores.md`;
they should avoid choices that would block what's below.

Builds on `app-updates.md` (#66: updates, parity, setup checks) and
`app-chores.md` (#73: sign-in, rebuild and chores as buttons). Those two are
the first slices of this one.

## Problem

Runway works on Joe's Mac because Claude sessions keep adjusting it: a path
here, a label there, a sign-in, a pull. Joe (2026-10-12): "if I could give it
to somebody else, they go through a setup wizard. Do they have Codex? Do they
have Claude? What plugins are they going to use? ... It gets all configured in
a UI and then runs, and then there is some way for it to create its own repo.
If it has problems, they can use Claude to manage the problems. They won't be
able to update the software, but they can at least get them through the
issues."

## Goal

A person with a Mac, a GitHub account and a Claude subscription downloads
Runway.app, and:

1. **Sets up in the app.** A wizard checks and installs what's needed, asks
   which optional tools and plugins to use, and never sends them to Terminal.
2. **Starts a project.** Either picks an existing repo or has Runway create a
   new private one, already set up for Runway.
3. **Runs.** The loop works their tickets as it does Joe's.
4. **Gets unstuck with Claude.** When something breaks, "Talk it through"
   opens Claude on the problem, and Claude can fix their setup and their repo.
   It doesn't change Runway's own code. When the cause is Runway itself, they
   report it, and the fix reaches them as an app update (#66).

## Rules

- **Their Runway is the same Runway.** No fork, no edition. Everything
  Joe-specific becomes a setting with a neutral default, and Joe's Mac keeps
  its current values in his own settings.
- **The engine is managed, not chosen.** The wizard clones the engine into
  `~/Library/Application Support/Runway/engine` and keeps it on `main`
  through "Update Runway" (#69). Joe can still point the Scripts setting at
  his own checkout. A stranger never needs to know the checkout exists.
- **Every install and sign-in is a button that runs as the user**, in the
  window's pane, with the command shown first (the #73 rules).
- **Required vs optional.** Required: macOS 14+, Xcode command line tools
  (`git`, `python3`; the engine is standard library only), Claude Code signed
  in, `gh` signed in (for the GitHub tracker), the pm plugin and Matt's skills.
  Optional, each with a line on what it adds: Codex (the codex harness, and
  the second review seat), Ringer (the two-seat panel review), Linear (as the
  tracker instead of GitHub Issues), and the other dc-dev-plugins plugins.
  A missing optional tool turns its feature off and says so. It never blocks.
- **Defaults a stranger can live with.** GitHub Issues tracker, private repo,
  `"review": "single"` unless Ringer is present, `"merge": "off"`,
  `"pr": "draft"`, Sonnet workers with an Opus option, a 10-minute tick, no
  quiet hours.
- **Fixing without patching.** "Talk it through" sessions run in the user's
  repo with the brief from `runway discuss`. The engine checkout is outside
  that repo and the session's brief says not to edit it. A "Report a Runway
  problem" action drafts a report (what happened, the log tail, versions,
  with paths under the home folder and repo names replaced) and shows it to
  the user before anything leaves the Mac. Where it goes is Joe's call (see
  Open questions).

## The wizard

Replaces the "Set up a loop…" sheet as the first-run window, and stays
reachable from the menu as "Set up a project…". Each step shows its checks,
each failing check has a fix button, and Next is enabled when the required
checks pass.

1. **Tools.** Xcode CLT, Claude Code (installed, signed in), `gh` (installed,
   signed in), Codex (optional). Fix buttons: `xcode-select --install`,
   Claude's official install command, `brew install gh` when Homebrew is
   present or the gh release download otherwise, the sign-ins.
2. **Plugins.** Adds the dc-dev-plugins marketplace and installs pm, and
   installs Matt's skills. Lists the other plugins in the marketplace with
   their descriptions as checkboxes, all off by default.
3. **Engine.** Clones it (or uses the setting). Shows its version line (#69).
4. **Project.** Existing: pick a folder that is a git repo with a GitHub
   remote. New: a name, an owner (their account or an org `gh` can see), and
   a folder. Runway runs `gh repo create <owner>/<name> --private --clone`,
   then commits a starter: `runway.json` from the template with this Mac's
   `park_authority`, a `CLAUDE.md` with the repo's check command, and
   `docs/specs/README.md`, then runs `runway setup` for the labels. Never
   makes a repo public. Never pushes to an existing repo without showing the
   diff first.
5. **How it runs.** Check command (detected from the repo where it can be:
   `package.json` test script, `pytest`, `swift test`, else asked), worker
   model, review mode, tick interval, quiet hours. Writes `runway.json`.
6. **Start.** Installs the loop's LaunchAgent (the Start button) and shows the
   first tick.

## What's Joe-specific today

| Where | Today | Becomes |
|---|---|---|
| `pm/runway/runway.py:2299`, `schedule.sh:12`, `ProjectDiscovery.swift:145` | LaunchAgent label `com.joe.runway.*` | `dev.datacraft.runway.*`. Discovery reads both, and Start rewrites an old label to the new one |
| `runway.py` tracker text (`Waiting on: Joe`, `Joe: go.`), label descriptions in `github_tracker.py`, app strings in `NeedsYou.swift`, `DecisionsTab.swift`, `SidePanel.swift` | "Joe" | `"owner_name"` in `runway.json` (the wizard fills it from `gh api user`), else "you" in the app and "the owner" in the tracker |
| `ringer_panel.py:36` | Ringer at `~/Agentic-Mini/_Core/Ringer` | `"ringer_path"` setting, else `ringer` on PATH, else panel review off |
| `Setup.swift` and `linear_tracker.py` | keychain item `runway-linear` | per-repo `keychain_service` (#71) |
| `Setup.swift:31`, Scripts setting | engine checkout picked by hand | managed clone (rule above) |
| `runway.json` `agent_cmd` | allowlist naming `bash factory/` and `swift` | the wizard writes the allowlist from the repo's check command |
| `pm/skills/runway/SKILL.md` | Astra, Ringer's grill-review kit, the cloud project | kept for Joe, worded as "if Ringer is set up"; the rest works without them |
| `make-app.sh` | ad-hoc signed | Developer ID and notarized (#67, #70). Without it, macOS won't open a downloaded copy |
| Joe's Mac auto mode, Marvin, the cloud project | how Joe drives it | not part of Runway; nothing may depend on them |

## Out of scope

- Windows and Linux.
- Runway hosting anything. Everything runs on the user's Mac, with their own
  accounts and their own model usage.
- Teams sharing one loop. One person, one Mac per repo, as today.
- The users changing Runway's code. They report problems instead.

## Open questions for Joe

1. **Where do other people's problem reports go?** Default in this draft: an
   issue on `datacraftdevelopment/dc-dev-plugins`, which is public, after the
   user reads the redacted report. Alternatives: email to Joe, or nowhere
   (Talk it through only).
2. **Who's first?** A specific person Joe will help set up, or anyone with
   the link. That decides how much the wizard has to explain, and whether
   notarization (#67) gates the first hand-off.

## Tickets (later, not filed)

Likely slices, in order: owner name and LaunchAgent label (engine plus app);
Ringer path and review default; managed engine clone; the wizard's Tools and
Plugins steps (extending #71); new-repo creation; runway.json from the wizard
(check command, allowlist); Report a Runway problem.
