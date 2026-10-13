import AppKit
import SwiftUI
import RunwayCore

@main
struct RunwayBarApp: App {
    @State private var store: ProjectStore
    private let notifier: Notifier
    @NSApplicationDelegateAdaptor(QuitGuard.self) private var quitGuard
    private let updater = AppUpdater()

    init() {
        // The store needs the notifier to deliver and the notifier needs the store to route clicks.
        var deliver: (([NotificationEvent]) -> Void)?
        let store = ProjectStore(deliver: { deliver?($0) })
        let notifier = Notifier(store: store)
        deliver = { notifier.deliver($0) }
        self.notifier = notifier
        store.appVersion = Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String
        store.start()
        store.updateOnLaunch(build: Bundle.main.object(forInfoDictionaryKey: "CFBundleVersion") as? String)
        QuitGuard.store = store
        _store = State(initialValue: store)
    }

    var body: some Scene {
        MenuBarExtra {
            RunwayMenu(store: store, updater: updater)
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
    let updater: AppUpdater
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
        ForEach(store.signInNeeds) { need in
            Button("Sign in to \(need.label)…") {
                guard let fix = need.fix, confirmRun(title: "Sign in to \(need.label)?", why: need.detail, line: fix) else { return }
                store.signIn(need)
                NSApplication.shared.activate(ignoringOtherApps: true)
                openWindow(id: "runway")
            }
            .disabled(need.fix == nil)
        }
        if !store.signInNeeds.isEmpty { Divider() }
        if store.entries.isEmpty {
            Text("No Runway projects found")
        }
        ForEach(store.entries) { entry in
            Menu("\(symbol(entry.status.state)) \(entry.status.name)  \(entry.status.detail)") {
                let project = entry.project
                if case .error = entry.status.state {
                    Button("Show error details") { show(project.label, ticket: nil, tab: .projects) }
                    Button("Talk it through") { Task { await store.talkThroughLoop(project); showSession() } }
                    if let failure = store.talkError(project: project, ticket: nil) { Text("⚠︎ \(String(failure.prefix(200)))") }
                    Divider()
                }
                if let repo = project.repoPath {
                    // A menu can't run show_if ahead of time without running checkout shell unasked, so only repo chores
                    // without one are offered here.
                    ForEach(store.choreList().chores.filter { $0.cwd == .repo && $0.showIf == nil }) { chore in
                        Button("\(chore.title)…") {
                            guard let line = store.choreLine(chore, repo: repo),
                                  confirmRun(title: "\(chore.title)?", why: chore.why, line: line) else { return }
                            store.runChore(chore, repo: repo)
                            NSApplication.shared.activate(ignoringOtherApps: true)
                            openWindow(id: "runway")
                        }
                        .help(store.choreLine(chore, repo: repo) ?? chore.run)
                    }
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
                ticketMenu(entry.project, id: ticket.id, title: ticket.title, errored: kind,
                           resumable: store.snapshot(for: entry.project.label)?.canResumeWorker(ticket.id) == true, tab: .decisions)
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
                ticketMenu(entry.project, id: row.id, title: row.title, errored: row.errored, resumable: row.resumable, tab: .queue)
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
        Picker("Open Claude sessions in", selection: Binding(get: { store.sessionPlace }, set: { store.setSessionPlace($0) })) {
            Text("Runway window").tag(SessionPlace.window)
            Text("Terminal").tag(SessionPlace.terminal)
        }
        Menu("Scripts") {
            Text(store.tools?.runwayScript ?? "Not found")
            Button("Choose dc-dev-plugins checkout…") { chooseCheckout() }
            Button("Use the one the plists point at") { store.setCheckout(nil) }
                .disabled(store.checkout == nil)
        }
        if let note = updater.state.menuNote {
            Text(note)
        } else {
            Button("Check for Updates…") { updater.checkForUpdates() }
        }
        updateSection
        Button("Quit") { NSApplication.shared.terminate(nil) }
            .keyboardShortcut("q")
    }

    /// The parity line, the Behind badge (whose action is Update Runway), the menu item and the last result.
    @ViewBuilder private var updateSection: some View {
        let behind = store.parity.behind
        Text(store.parity.line)
        if !behind.isEmpty {
            Button("⬆︎ Behind: \(behind.joined(separator: "; ")) — Update Runway") { store.requestUpdate() }
                .disabled(store.updatePending || store.updating)
        }
        Button(store.updating ? "Updating Runway…" : store.updatePending ? "Update Runway (waits for the tick)" : "Update Runway")
            { store.requestUpdate() }
            .disabled(store.updatePending || store.updating)
        if let result = store.updateResult {
            Text(String(result.summary.prefix(400)))
            if result != .waiting { Button("Dismiss") { store.dismissUpdateResult() } }
        }
    }

    /// One waiting or errored ticket: a submenu with where it lives and the "Talk it through" button.
    @ViewBuilder private func ticketMenu(_ project: Project, id: String, title: String, errored: String?,
                                         resumable: Bool, tab: NotificationTab) -> some View {
        let flag = errored.map { "  ⚑ \(ErroredKind.words($0))" } ?? ""
        Menu("\(id) \(title)\(flag)") {
            Button(tab == .decisions ? "Open decision" : "Show details") { show(project.label, ticket: id, tab: tab) }
            Button("Talk it through") { Task { await store.talkThrough(ticket: id, in: project); showSession() } }
            if let failure = store.talkError(project: project, ticket: id) { Text("⚠︎ \(String(failure.prefix(200)))") }
            if resumable {
                Button("Resume worker") { Task { await store.resumeWorker(ticket: id, in: project); showSession() } }
                if let failure = store.talkError(project: project, ticket: id, resume: true) { Text("⚠︎ \(String(failure.prefix(200)))") }
            }
        }
    }

    /// A session opened in the window needs the window in front.
    private func showSession() {
        guard store.sessionPlace == .window else { return }
        NSApplication.shared.activate(ignoringOtherApps: true)
        openWindow(id: "runway")
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

/// The menu's one look before a command runs: what it's for and the exact line, with Run or Cancel.
/// The panel and the This Mac sheet show the line beside the button; a menu item can't.
@MainActor
func confirmRun(title: String, why: String, line: String) -> Bool {
    NSApplication.shared.activate(ignoringOtherApps: true)
    let alert = NSAlert()
    alert.messageText = title
    alert.informativeText = (why.isEmpty ? "" : why + "\n\n") + "Runs in the Runway window:\n" + line
    alert.addButton(withTitle: "Run")
    alert.addButton(withTitle: "Cancel")
    return alert.runModal() == .alertFirstButtonReturn
}
