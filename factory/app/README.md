# Runway app

Menu bar app for Runway. Swift package, no Xcode project, no third-party dependencies. macOS 14+.

- `RunwayCore`: models and file parsing, no SwiftUI. Unit tested.
- `RunwayBar`: SwiftUI `MenuBarExtra` app. Placeholder menu for now ("Runway" + Quit).

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
