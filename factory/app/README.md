# Runway app

Menu bar app for Runway. Swift package, no Xcode project, no third-party dependencies. macOS 14+.

- `RunwayCore`: models, file parsing, state logic and command builders, no SwiftUI. Unit tested.
  - `RunState.swift`: heartbeat + launchctl + pause file + decisions waiting → per-project and overall state. A heartbeat in an active phase whose pid is gone is an error, not running.
  - `Commands.swift`: Start = `schedule.sh install <repo> <minutes>`, Stop = `schedule.sh uninstall <repo>`, Run now = `launchctl kickstart gui/<uid>/<label>`, Pause/Resume = `runway.py pause|resume`. A failed command shows its stderr at the top of the menu.
- `RunwayBar`: SwiftUI `MenuBarExtra` app. Icon follows the overall state (airplane running, bell waiting on you, pause, moon all off, triangle error) with a count of decisions waiting. One submenu per project; Pause all loops / Resume; Scripts.

Notifications (`Notifications.swift` in RunwayCore, delivery in `RunwayBar/Notifier.swift`): once per decision packet, once per ticket parked after a failed retry, and once per project with ready tickets but its loop off (repeat at most every 4 hours, never in quiet hours from `~/.runway/machine.json`). What was notified is remembered in `~/Library/Application Support/Runway/notified.json`, so a restart doesn't repeat it; a ticket that is answered and later parked again notifies again. The icon turns amber for ready-work-while-off whether or not notifications are allowed. Notifications need the bundled app (`make-app.sh`). A click records the tab to open (`ProjectStore.requestedRoute`); the app has no window yet, so nothing shows it.

Window (`RunwayBar/RunwayWindow.swift`, opened from the menu's "Open Runway window"): project sidebar with state dots and decision badges, a title bar with the state pill, interval, Start/Stop and Run a tick now (the menu's actions), and tabs Now / Queue / Decisions / Runs. All four tabs are built. Now shows banners, working on, elapsed and attempt, next tick (last tick start + StartInterval), the sync→merge phase strip and the last 30 lines of `_pm/runway.log`. The math (`NowMath`) and the log reader (`LogTail`, which reads only appended bytes and starts from the last 64 KB of a big file) live in `RunwayCore/NowTab.swift`. A project that never ran has no heartbeat or log and shows "Nothing right now", "—" and "No log yet."

`schedule.sh` and `runway.py` are found from the Scripts setting (a dc-dev-plugins checkout), else from the `runway.py` path in the LaunchAgent plists. The script path is remembered, so a stopped loop keeps its row and can be started again. Decisions waiting come from `runway.py status --json`, polled at most once a minute. "Until tomorrow 08:00" means the next 08:00, so before 08:00 it ends this morning.

Runs tab (`RunwayCore/RunsTab.swift`, `RunwayBar/RunsTabView.swift`): `_pm/runway-runs.jsonl` as a table, newest first (when, ticket, kind, harness, attempt, result, minutes, tokens = input+output, cost) with a totals footer summed from the same rows. Result: an agent call passes on exit 0, `finish` on `check_exit` 0, `outcome` reads `done` as pass and `needs-human`/`stopped` as park. Missing fields show "—" and bad lines are skipped. Session reveals `~/.claude/projects/*/<session_id>.jsonl` in Finder. "Write retro prompt" runs `runway retro` and opens `_pm/runway-retro-prompt.md`. `_pm/runway-pr.md`, when present, shows under "Finish". The log is parsed off the main actor and re-read every 10 seconds.

Decisions tab (`RunwayCore/DecisionsTab.swift`, `RunwayBar/DecisionsTabView.swift`): one card per ticket in the `waiting` group of `status --json`, the packet drawn from Markdown blocks (`PacketMarkdown`: headings, lists, code; inline bold and links via `AttributedString`; lines saying "recommend…" get a badge). A note field plus Go and No buttons run `runway go|no <ticket> "<note>"` as Joe (Joe confirmed 2026-10-07 that a Go click counts as his go; it posts his comment to Linear). The buttons are the only thing that runs it, once per ticket. Then status refreshes and the card says "Answered: go “note”, picked up on the next tick", and stays until the tab is left. A failure shows the command output and records no answer. The menu bar dropdown lists waiting decisions and opens this tab.

Set up a loop sheet (`RunwayCore/Setup.swift`, `RunwayBar/SetupSheetView.swift`), from "Set up a loop…" at the bottom of the sidebar. It checks this Mac (`SetupChecks`: Python 3.9+, git, `claude --version`, optional `codex` / `cursor-agent`, the engine checkout, the `runway-linear` keychain item) through a login shell, so the PATH matches what the loop sees. Sign-in can't be checked silently, so "Open Terminal to sign in" opens Terminal running `claude`. A missing engine offers "Clone…" (dc-dev-plugins into a folder you pick). The Linear key is saved with `security add-generic-password -U -s runway-linear`; it is only held in the secure field until saved, is masked in the command shown, is scrubbed from any output, and is never written to a file or log (`security` has no stdin form, so it is briefly in that process's arguments). The steps are a list (`SetupPlan.steps`, `SetupStep`), shown first, then run in order with output streamed: `setup.sh`, `runway setup`, a claim check, `schedule.sh install`. A git tracker only installs the schedule. The claim check reads `runway status --json` and warns about tickets stamped by another machine (DAT-11); it never stops the flow. A failed step stops the flow and shows what it printed; every step is safe to repeat, so "Run again" starts from the top. A non-claude harness needs a matching `harnesses` profile in `runway.json` (else the engine falls back to claude), so that step refuses and says so.

## Build, run, test

```bash
cd factory/app
swift build            # debug build
swift test             # RunwayCore unit tests
./make-app.sh          # release build -> build/Runway.app
open build/Runway.app  # menu bar item, no Dock icon (LSUIElement)
bash make-app.sh --install  # build, copy to /Applications/Runway.app and open it
```

`make-app.sh` prints the Login Items steps: System Settings > General > Login Items & Extensions > `+` > pick `build/Runway.app`.

## Check command

`factory/scripts/check.sh` already runs `swift test` in `factory/app` once `Package.swift` exists, so the repo's `runway.json` `check_cmd` (`bash factory/scripts/check.sh`) covers the app. If you use a different `check_cmd`, include `(cd factory/app && swift test)`.

Install with `bash make-app.sh --install` (puts it in `/Applications`). The engine opens it in the background whenever a `tick`, `loop` or `finish` starts and it isn't running (`ensure_app` in `runway.py`; `RUNWAY_NO_APP=1` turns that off).
