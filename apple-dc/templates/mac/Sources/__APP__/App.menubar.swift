import AppKit
import SwiftUI

@main
struct __APP__App: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) private var delegate

    var body: some Scene {
        MenuBarExtra("__DISPLAY__", systemImage: "app.dashed") {
            ContentView()
            Divider()
            UpdatesMenuItem()
            Button("Quit __DISPLAY__") { NSApp.terminate(nil) }
                .keyboardShortcut("q")
        }
    }
}

final class AppDelegate: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ notification: Notification) {
        Task { @MainActor in
            _ = AppUpdater.shared
            // Run from Downloads or the disk image: offer the move first, since updates only work from Applications.
            MoveToApplications.offerIfNeeded()
        }
    }
}

/// "Check for Updates…", or a note saying why updates are off in this build.
struct UpdatesMenuItem: View {
    var body: some View {
        if let note = AppUpdater.shared.state.menuNote {
            Text("__DISPLAY__ \(AppUpdater.shared.version) · \(note)")
        } else {
            Button("Check for Updates…") { AppUpdater.shared.checkForUpdates() }
        }
    }
}

struct ContentView: View {
    var body: some View {
        Text("__DISPLAY__ \(AppUpdater.shared.version)")
    }
}
