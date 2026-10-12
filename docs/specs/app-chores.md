# Spec: Runway's routine chores happen in the app, not in Terminal

Tracker entry: #73 (tickets #74-#77, its sub-issues).

Companion to `app-updates.md` (#66). That spec covers updating: the app
updating itself, "Update Runway" pulling the engine checkout and updating pm,
and the setup sheet for a new Mac. This one covers the rest of the Terminal
trips.

## Problem

Joe keeps leaving the app for Terminal to do something small, then coming back
to see whether it worked (Joe, 2026-10-12: "less of this jumping into terminal,
getting a thing going, and coming back"). The trips from the last few days:

| Trip | Where it goes |
|---|---|
| `claude auth login` after the loop's sign-in expired. The loop logged "needs signing in" every tick for hours, and nothing in the app asked Joe to act. | **#74, #75** |
| `git pull --ff-only` on the checkout so Runway sees a new spec | #69 (Update Runway) |
| `/plugin marketplace update`, plugin update, uninstalling retired plugins | #69, and a chore (#77) |
| `bash factory/app/make-app.sh --install` to rebuild the app | #68 once releases exist; **#76** until then |
| `python3 scripts/refresh_codex.py --install` / `--check` | **Chore, #77** |
| Start did nothing after the engine moved, the error was hidden in the menu | #64 |
| Creating the `harness:opus` label | Done on 2026-10-12 |

Agents can't do these for Joe: his Mac's auto mode blocks an agent from
signing in, rebuilding the app, or changing plugins and `~/.codex`. A button
Joe clicks in the app runs as Joe, so the app is the place for them.

## Rules

- **The app holds no logic.** It runs a named command and shows its output.
  What a check means and what fixes it comes from the engine (`runway.py`) or
  from a file in the checkout, so a new chore doesn't need a new app build.
- **Interactive commands run in the window's pane**, the SwiftTerm pane "Talk it
  through" already uses (`SessionPane.swift`, `Sessions.swift`), through a login
  shell (`/bin/zsh -lc`) so PATH matches the loop. A pane tab for a chore is
  titled with the chore's name. "Pop out to Terminal" still works for it.
  The Setup sheet's existing sign-in buttons (`Setup.signInCommand`,
  `Setup.ghLoginCommand`), which open Terminal.app today, move to the pane too.
- **Show the command first.** Before a chore or a sign-in runs, the app shows
  the exact command line and where it runs. One click runs it. A chore marked
  `confirm` asks again first.
- **Check after.** When a sign-in or chore's process exits, the app re-runs the
  check that raised it and shows the new result next to the button: "Signed in"
  or the failing detail. Never "done" on exit code alone.
- **Signed out is a "Needs you" item.** When `status --json` reports a failing
  sign-in check, or a pause the engine set because an agent call failed on auth,
  the side panel's "Needs you" section shows it first, the menu bar icon shows
  the needs-you badge, and one notification goes out (the engine already sends
  it; the app doesn't send a second). The item names the tool ("Claude Code is
  signed out") and has a "Sign in" button that runs that check's fix command.
- **Resume only what sign-in paused.** After every failing check passes, the
  app clears the pause only when the engine set it for sign-in. A pause Joe set
  himself stays.
- **Never widen anything.** No chore changes a worker's permissions, the
  `agent_cmd` allowlist, a LaunchAgent (Start and Stop stay the only buttons
  that touch those), or a repo other than the engine checkout.

## Engine changes (#74)

- Each check in `status --json`'s `signin.checks` (and in
  `_pm/runway-signin.json`) gains `"label"` (e.g. "Claude Code") and `"fix"`
  (the command line, e.g. `claude auth login`). `detail` keeps its text.
- `runway signin [--json]` runs the checks the next tick would run, the same as
  `signin_checks`, as if work were waiting, and writes `_pm/runway-signin.json`.
  It never claims or preps anything, and never makes a model call. Exit 0 when
  all pass.
- The pause file gains `"reason"`: `"signed-out"` when `pause_for_auth` writes
  it, absent otherwise. `status --json`'s `paused` carries it.
- `runway resume --if-reason signed-out` deletes the pause only when its reason
  matches, and prints what it did either way. Plain `runway resume` is unchanged.
- The module docstring documents all of this, as it does today for the fields.

## Rebuild from the checkout (#76)

Until signed releases exist (#67, #70), and on a Mac without the Sparkle key,
the app can rebuild itself from the checkout:

- `make-app.sh` records the commit it built from (`git rev-parse --short HEAD`)
  as `RunwayBuildCommit` in `Info.plist`, next to #68's version keys.
- The parity line from #69 shows that commit. When the checkout has commits
  under `factory/app/` newer than it (`git log <built>..HEAD -- factory/app`),
  the Behind badge offers "Rebuild Runway".
- "Rebuild Runway" runs `make-app.sh --install` detached from the app
  (`/bin/zsh -lc`, its own process group, output to
  `~/Library/Logs/Runway/rebuild.log`), because `--install` quits the running
  app. The app says "Rebuilding… Runway will reopen" and quits itself only
  after the build step succeeds. A failed build leaves the running app alone
  and shows the log's tail in the window.
- Once the updater is on (a key is present and the feed has a release), the
  Behind badge offers the update instead, and "Rebuild Runway" moves under
  Scripts in the menu for anyone working on the app.

## Chores (#77)

`pm/runway/chores.json` in the checkout lists named chores. The app reads it
from the checkout in its Scripts setting; it is data, never code the app runs
other than the listed command.

```json
{"version": 1, "chores": [
  {"id": "codex-refresh", "title": "Refresh Codex plugins",
   "why": "Rebuilds the Codex edition of the plugins and installs it",
   "run": "python3 scripts/refresh_codex.py --install && python3 scripts/refresh_codex.py --check",
   "cwd": "checkout", "show_if": "command -v codex", "confirm": true},
  {"id": "retired-plugins", "title": "Remove retired plugins",
   "why": "sdlc, ui-test and factory now live in pm",
   "run": "for p in sdlc ui-test factory; do claude plugin uninstall \"$p@dc-dev-plugins\" 2>/dev/null; done; claude plugin list",
   "cwd": "checkout",
   "show_if": "claude plugin list | grep -Eq '(sdlc|ui-test|factory)@dc-dev-plugins'"},
  {"id": "tracker-setup", "title": "Check tracker setup", "run": "runway setup",
   "cwd": "repo", "per_repo": true}
]}
```

- `cwd` is `checkout` (the engine checkout) or `repo` (a loop's repo, which
  makes the chore appear per project).
- `show_if` is a status command. Exit 0 shows the chore; anything else hides
  it. It never makes a model call and has a 10 s timeout.
- The Machine sheet gets a "Chores" section listing them, each with its `why`,
  a Run button and the last result. Per-repo chores also appear in that
  project's menu.
- Initial chores: Refresh Codex plugins, Remove retired plugins (uninstalls
  any of `sdlc`, `ui-test`, `factory` from dc-dev-plugins that `claude plugin
  list` still shows), Check tracker setup (`runway --root <repo> setup`).

## Out of scope

- Anything #66's tickets already do (updates, parity, new-Mac setup).
- Answering a ticket (Go/No and Talk it through already exist).
- Changing worker permissions from the app. That stays a deliberate edit to
  `runway.json`.
- Running chores on a schedule. Every chore is a click.

## Tickets

1. #74 **Engine: sign-in checks name their fix, `runway signin`, pause reason**
   (`ready-for-agent`).
2. #75 **App: signed out shows in Needs you, and Sign in runs in the pane**
   (`ready-for-agent`, `harness:opus`, blocked by #74). Includes moving the Setup
   sheet's sign-in buttons into the pane, and the shared "run a command in the
   pane, then re-check" piece #77 reuses.
3. #76 **App: Rebuild Runway from the checkout** (`ready-for-agent`, blocked by #68
   and #69, which change `make-app.sh` and add the parity line).
4. #77 **Chores list and the Machine sheet's Chores section** (`ready-for-agent`,
   blocked by #75).

Order: #74 → #75 → #77; #76 after #68 and #69. #64 should run before #75, since both
touch how a failed command shows in the window.
