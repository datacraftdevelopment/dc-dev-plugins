import SwiftUI
import RunwayCore

@main
struct RunwayBarApp: App {
    @State private var store: ProjectStore

    init() {
        let store = ProjectStore()
        store.start()
        _store = State(initialValue: store)
    }

    var body: some Scene {
        MenuBarExtra(RunwayInfo.menuTitle, systemImage: "airplane") {
            if store.projects.isEmpty {
                Text("No Runway projects found")
            }
            ForEach(store.projects) { project in
                Text(label(for: project))
            }
            Divider()
            Button("Quit") { NSApplication.shared.terminate(nil) }
                .keyboardShortcut("q")
        }
    }

    private func label(for project: Project) -> String {
        if let error = project.error { return "⚠︎ \(project.name) — \(error)" }
        if !project.loaded { return "○ \(project.name)" }
        if let exit = project.lastExit, exit != 0 { return "⚠︎ \(project.name) — exit \(exit)" }
        return "● \(project.name)"
    }
}
