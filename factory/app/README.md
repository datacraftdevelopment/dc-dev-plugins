# Runway app

Menu bar app for Runway. Swift package, no Xcode project, no third-party dependencies. macOS 14+.

- `RunwayCore`: models, file parsing, state logic and command builders, no SwiftUI. Unit tested.
  - `RunState.swift`: heartbeat + launchctl + pause file + decisions waiting → per-project and overall state. A heartbeat in an active phase whose pid is gone is an error, not running.
  - `Commands.swift`: Start = `schedule.sh install <repo> <minutes>`, Stop = `schedule.sh uninstall <repo>`, Run now = `launchctl kickstart gui/<uid>/<label>`, Pause/Resume = `runway.py pause|resume`. A failed command shows its stderr at the top of the menu.
- `RunwayBar`: SwiftUI `MenuBarExtra` app. Icon follows the overall state (airplane running, bell waiting on you, pause, moon all off, triangle error) with a count of decisions waiting. One submenu per project; Pause all loops / Resume; Scripts.

Notifications (`Notifications.swift` in RunwayCore, delivery in `RunwayBar/Notifier.swift`): once per decision packet, once per ticket parked after a failed retry, and once per project with ready tickets but its loop off (repeat at most every 4 hours, never in quiet hours from `~/.runway/machine.json`). What was notified is remembered in `~/Library/Application Support/Runway/notified.json`, so a restart doesn't repeat it; a ticket that is answered and later parked again notifies again. The icon turns amber for ready-work-while-off whether or not notifications are allowed. Notifications need the bundled app (`make-app.sh`). A click records the tab to open (`ProjectStore.requestedRoute`); the app has no window yet, so nothing shows it.

Window (`RunwayBar/RunwayWindow.swift`, opened from the menu's "Open Runway window"): project sidebar with state dots and decision badges, a title bar with the state pill, interval, Start/Stop and Run a tick now (the menu's actions), and tabs Now / Queue / Decisions / Runs. Only Now is built; the others say "coming soon". Now shows banners, working on, elapsed and attempt, next tick (last tick start + StartInterval), the sync→merge phase strip and the last 30 lines of `_pm/runway.log`. The math (`NowMath`) and the log reader (`LogTail`, which reads only appended bytes and starts from the last 64 KB of a big file) live in `RunwayCore/NowTab.swift`. A project that never ran has no heartbeat or log and shows "Nothing right now", "—" and "No log yet."

`schedule.sh` and `runway.py` are found from the Scripts setting (a dc-dev-plugins checkout), else from the `runway.py` path in the LaunchAgent plists. The script path is remembered, so a stopped loop keeps its row and can be started again. Decisions waiting come from `runway.py status --json`, polled at most once a minute. "Until tomorrow 08:00" means the next 08:00, so before 08:00 it ends this morning.

## Build, run, test

```bash
cd factory/app
swift build            # debug build
swift test             # RunwayCore unit tests
./make-app.sh          # release build -> build/Runway.app
open build/Runway.app  # menu bar item, no Dock icon (LSUIElement)
```

`make-app.sh` prints the Login Items steps: System Settings > General > Login Items & Extensions > `+` > pick `build/Runway.app`.

## Check command

`factory/scripts/check.sh` already runs `swift test` in `factory/app` once `Package.swift` exists, so the repo's `runway.json` `check_cmd` (`bash factory/scripts/check.sh`) covers the app. If you use a different `check_cmd`, include `(cd factory/app && swift test)`.
