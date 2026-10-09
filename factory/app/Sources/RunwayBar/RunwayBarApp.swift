import AppKit
import SwiftUI
import RunwayCore

@main
struct RunwayBarApp: App {
    @State private var store: ProjectStore
    private let notifier: Notifier

    init() {
        // The store needs the notifier to deliver and the notifier needs the store to route clicks.
        var deliver: (([NotificationEvent]) -> Void)?
        let store = ProjectStore(deliver: { deliver?($0) })
        let notifier = Notifier(store: store)
        deliver = { notifier.deliver($0) }
        self.notifier = notifier
        store.start()
        _store = State(initialValue: store)
    }

    var body: some Scene {
        MenuBarExtra {
            RunwayMenu(store: store)
        } label: {
            HStack(spacing: 2) {
                icon
                if store.badge > 0 { Text("\(store.badge)") }
            }
        }
        Window("Runway", id: "runway") {
            RunwayWindow(store: store)
        }
        Window("Runway panel", id: "runway-panel") {
            SidePanel(store: store)
        }
        .defaultSize(width: 300, height: 760)
        .windowResizability(.contentSize)
    }

    /// Amber when a project has ready tickets but its loop is off. Errors and decisions waiting keep their own icon.
    @ViewBuilder private var icon: some View {
        let amber = store.readyWhileOff && (store.overall == .allOff || store.overall == .running)
        if amber, let image = NSImage(systemSymbolName: "airplane.departure", accessibilityDescription: "Ready work, loop off")?
            .withSymbolConfiguration(.init(paletteColors: [.systemOrange])) {
            Image(nsImage: image)
        } else {
            Image(systemName: iconName(store.overall))
        }
    }

    private func iconName(_ state: OverallState) -> String {
        switch state {
        case .running: return "airplane"
        case .waiting: return "bell.badge"
        case .paused: return "pause.circle"
        case .allOff: return "moon.zzz"
        case .error: return "exclamationmark.triangle"
        }
    }
}

struct RunwayMenu: View {
    let store: ProjectStore
    @Environment(\.openWindow) private var openWindow

    var body: some View {
        Button("Open Runway window") {
            NSApplication.shared.activate(ignoringOtherApps: true)
            openWindow(id: "runway")
        }
        Button("Open side panel") {
            NSApplication.shared.activate(ignoringOtherApps: true)
            openWindow(id: "runway-panel")
        }
        Divider()
        if let error = store.lastError {
            Text("⚠︎ \(String(error.prefix(300)))")
            Button("Dismiss") { store.dismissError() }
            Divider()
        }
        if store.entries.isEmpty {
            Text("No Runway projects found")
        }
        ForEach(store.entries) { entry in
            Menu("\(symbol(entry.status.state)) \(entry.status.name)  \(entry.status.detail)") {
                let project = entry.project
                if case .error = entry.status.state {
                    Button("Show error details") { show(project.label, ticket: nil, tab: .projects) }
                    Button("Talk it through") { Task { await store.talkThroughLoop(project) } }
                    if let failure = store.talkError(project: project, ticket: nil) { Text("⚠︎ \(String(failure.prefix(200)))") }
                    Divider()
                }
                let canStart = project.repoPath != nil && !project.loaded
                Button("Start loop") { Task { await store.startLoop(project) } }
                    .disabled(!canStart || project.error != nil)
                Button("Stop loop") { Task { await store.stopLoop(project) } }
                    .disabled(!project.loaded)
                Button("Run a tick now") { Task { await store.runNow(project) } }
                    .disabled(!project.loaded)
            }
        }
        let waiting = store.entries.flatMap { entry in
            (store.snapshot(for: entry.project.label)?.tickets ?? []).map { (entry, $0) }
        }
        if !waiting.isEmpty {
            Divider()
            Text("Decisions waiting")
            ForEach(waiting, id: \.1.id) { entry, ticket in
                let kind = store.snapshot(for: entry.project.label)?.errored[ticket.id]
                ticketMenu(entry.project, id: ticket.id, title: ticket.title, errored: kind, tab: .decisions)
            }
        }
        // Errored tickets that aren't waiting come under the waiting ones.
        let errored = store.entries.flatMap { entry in
            (store.snapshot(for: entry.project.label)?.needsYou ?? []).filter { !$0.waiting }.map { (entry, $0) }
        }
        if !errored.isEmpty {
            Divider()
            Text("Errored tickets")
            ForEach(errored, id: \.1.id) { entry, row in
                ticketMenu(entry.project, id: row.id, title: row.title, errored: row.errored, tab: .queue)
            }
        }
        Divider()
        if store.pause != nil {
            Button("Resume") { Task { await store.resume() } }
        } else {
            Menu("Pause all loops") {
                Button("For 1 hour") { Task { await store.pauseAll(.oneHour) } }
                Button("Until tomorrow 08:00") { Task { await store.pauseAll(.untilTomorrow) } }
                Button("Until I resume") { Task { await store.pauseAll(.untilResumed) } }
            }
        }
        if !store.hiddenProjects.isEmpty {
            Menu("Hidden projects") {
                ForEach(store.hiddenProjects) { project in
                    Button("Show \(project.name)") { store.unhide(project.label) }
                }
            }
        }
        Divider()
        Menu("Scripts") {
            Text(store.tools?.runwayScript ?? "Not found")
            Button("Choose dc-dev-plugins checkout…") { chooseCheckout() }
            Button("Use the one the plists point at") { store.setCheckout(nil) }
                .disabled(store.checkout == nil)
        }
        Button("Quit") { NSApplication.shared.terminate(nil) }
            .keyboardShortcut("q")
    }

    /// One waiting or errored ticket: a submenu with where it lives and the "Talk it through" button.
    @ViewBuilder private func ticketMenu(_ project: Project, id: String, title: String, errored: String?,
                                         tab: NotificationTab) -> some View {
        let flag = errored.map { "  ⚑ \(ErroredKind.words($0))" } ?? ""
        Menu("\(id) \(title)\(flag)") {
            Button(tab == .decisions ? "Open decision" : "Open in queue") { show(project.label, ticket: id, tab: tab) }
            Button("Talk it through") { Task { await store.talkThrough(ticket: id, in: project) } }
            if let failure = store.talkError(project: project, ticket: id) { Text("⚠︎ \(String(failure.prefix(200)))") }
        }
    }

    private func show(_ label: String, ticket: String?, tab: NotificationTab) {
        store.requestedRoute = NotificationRoute(projectLabel: label, ticketID: ticket, tab: tab)
        NSApplication.shared.activate(ignoringOtherApps: true)
        openWindow(id: "runway")
    }

    private func symbol(_ state: RunState) -> String {
        switch state {
        case .running: return "▶︎"
        case .waiting: return "●"
        case .paused: return "⏸"
        case .idle: return "○"
        case .off: return "◌"
        case .error: return "⚠︎"
        }
    }

    private func chooseCheckout() {
        NSApplication.shared.activate(ignoringOtherApps: true)
        let panel = NSOpenPanel()
        panel.canChooseDirectories = true
        panel.canChooseFiles = false
        panel.prompt = "Choose"
        panel.message = "Pick the dc-dev-plugins checkout (the folder that contains factory/)."
        if panel.runModal() == .OK, let url = panel.url { store.setCheckout(url.path) }
    }
}
