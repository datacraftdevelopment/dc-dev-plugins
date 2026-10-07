import SwiftUI
import RunwayCore

@main
struct RunwayBarApp: App {
    var body: some Scene {
        MenuBarExtra(RunwayInfo.menuTitle, systemImage: "airplane") {
            Text(RunwayInfo.menuTitle)
            Divider()
            Button("Quit") { NSApplication.shared.terminate(nil) }
                .keyboardShortcut("q")
        }
    }
}
