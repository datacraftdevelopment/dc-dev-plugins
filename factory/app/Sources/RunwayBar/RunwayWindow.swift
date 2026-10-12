import SwiftUI
import RunwayCore

enum RunwayTab: String, CaseIterable, Identifiable {
    case board = "Board", runs = "Runs"
    var id: String { rawValue }
}

struct RunwayWindow: View {
    let store: ProjectStore
    @State private var selection: String?
    @State private var tab: RunwayTab = .board
    /// The board card whose details are open, if any.
    @State private var selectedTicket: String?
    /// A routed ticket waiting for its project's selection to land, so the project switch doesn't clear it.
    @State private var pendingTicket: String?
    @State private var showSetup = false
    @State private var showMachine = false
    @Environment(\.openWindow) private var openWindow

    private var entry: ProjectEntry? {
        store.entries.first { $0.project.label == selection } ?? store.entries.first
    }

    var body: some View {
        NavigationSplitView {
            List(store.entries, selection: $selection) { entry in
                HStack(spacing: 8) {
                    Circle().fill(color(entry.status.state)).frame(width: 8, height: 8)
                    VStack(alignment: .leading, spacing: 1) {
                        Text(entry.status.name)
                        Text(pillText(entry.status)).font(.caption).foregroundStyle(.secondary)
                    }
                    Spacer()
                    if entry.status.waiting > 0 {
                        Text("\(entry.status.waiting)")
                            .font(.caption.bold()).foregroundStyle(.white)
                            .padding(.horizontal, 6).background(.orange, in: Capsule())
                    }
                    if entry.status.errored > 0 {
                        Label("\(entry.status.errored)", systemImage: "flag.fill")
                            .font(.caption.bold()).foregroundStyle(.red)
                            .help("Tickets whose latest attempt didn't merge")
                    }
                }
                .padding(.vertical, 2)
                .tag(entry.project.label)
                .contextMenu {
                    Button("Hide from Runway") { store.hide(entry.project.label) }
                }
            }
            .navigationSplitViewColumnWidth(min: 180, ideal: 210)
            .safeAreaInset(edge: .bottom) {
                VStack(alignment: .leading, spacing: 2) {
                    Divider().padding(.bottom, 4)
                    Button { showSetup = true } label: { Label("Set up a loop…", systemImage: "plus.circle") }
                    Button { showMachine = true } label: { Label("This Mac…", systemImage: "desktopcomputer") }
                    if !store.hiddenProjects.isEmpty {
                        Menu {
                            ForEach(store.hiddenProjects) { project in
                                Button("Show \(project.name)") { store.unhide(project.label) }
                            }
                        } label: { Label("Hidden (\(store.hiddenProjects.count))", systemImage: "eye.slash") }
                        .menuStyle(.borderlessButton).fixedSize()
                    }
                }
                .buttonStyle(.borderless).foregroundStyle(.secondary)
                .padding(.horizontal, 12).padding(.bottom, 10).frame(maxWidth: .infinity, alignment: .leading)
            }
            .sheet(isPresented: $showSetup) { SetupSheet(store: store) }
            .sheet(isPresented: $showMachine) { MachineSheet(store: store) }
        } detail: {
            if let entry {
                VStack(spacing: 0) {
                  VStack(spacing: 0) {
                    Picker("", selection: $tab) {
                        ForEach(RunwayTab.allCases) { Text($0.rawValue).tag($0) }
                    }
                    .pickerStyle(.segmented).labelsHidden().padding(10)
                    Divider()
                    if tab == .board {
                        BoardTab(store: store, entry: entry, selected: $selectedTicket).id(entry.project.label)
                    } else {
                        RunsTab(store: store, entry: entry)
                    }
                  }
                  if !store.sessions.sessions.isEmpty {
                      Divider()
                      SessionPane(store: store)
                  }
                }
                .toolbar { toolbar(for: entry) }
                .navigationTitle(entry.status.name)
            } else {
                Text("No Runway projects found").foregroundStyle(.secondary)
            }
        }
        .frame(minWidth: 760, minHeight: 480)
        .onChange(of: store.requestedRoute) { _, _ in applyRoute() }
        // Picking another project closes the details pane; one in error lands on the board, where the error is at the top.
        .onChange(of: selection) { _, label in
            selectedTicket = pendingTicket
            pendingTicket = nil
            if let label, let picked = store.entries.first(where: { $0.project.label == label }),
               case .error = picked.status.state { tab = .board }
        }
        // A route set from the menu while the window was closed is already there when the window opens.
        .onAppear { applyRoute() }
    }

    private func applyRoute() {
        guard let route = store.requestedRoute else { return }
        // Every route lands on the board now: Decisions and Queue are its columns, and the ticket's details open.
        tab = .board
        if selection == route.projectLabel {
            selectedTicket = route.ticketID
        } else {
            pendingTicket = route.ticketID
            selection = route.projectLabel
        }
        store.requestedRoute = nil
    }

    @ToolbarContentBuilder private func toolbar(for entry: ProjectEntry) -> some ToolbarContent {
        let project = entry.project
        ToolbarItem(placement: .navigation) {
            Button { openWindow(id: "runway-panel") } label: { Label("Side panel", systemImage: "sidebar.right") }
                .help("Open the side panel")
        }
        ToolbarItem {
            StatePill(state: entry.status.state, text: pillText(entry.status),
                      detail: project.interval.map { "every \(max(1, $0 / 60)) min" })
        }
        ToolbarItemGroup {
            if project.loaded {
                Button { Task { await store.stopLoop(project) } } label: { Label("Stop", systemImage: "stop.fill") }
                    .help("Stop this loop").labelStyle(.titleAndIcon)
            } else {
                Button { Task { await store.startLoop(project) } } label: { Label("Start", systemImage: "play.fill") }
                    .help("Start this loop").labelStyle(.titleAndIcon)
                    .disabled(project.repoPath == nil || project.error != nil)
            }
            Button { Task { await store.runNow(project) } } label: {
                Label("Run a tick now", systemImage: "forward.end.fill")
            }
            .help("Run a tick now").labelStyle(.titleAndIcon)
            .disabled(!project.loaded)
        }
    }
}

func pillText(_ status: ProjectStatus) -> String {
    switch status.state {
    case .running: return "Running"
    case .waiting: return "Waiting on you"
    case .paused: return "Paused"
    case .idle: return "Idle"
    case .off: return "Off"
    case .error: return "Error"
    }
}

func color(_ state: RunState) -> Color {
    switch state {
    case .running: return .green
    case .waiting: return .orange
    case .paused: return .yellow
    case .idle: return .blue
    case .off: return .gray
    case .error: return .red
    }
}

struct StatePill: View {
    let state: RunState
    let text: String
    var detail: String? = nil

    var body: some View {
        HStack(spacing: 6) {
            Circle().fill(color(state)).frame(width: 7, height: 7)
            Text(text).font(.callout.weight(.medium))
            if let detail {
                Text("·").foregroundStyle(.tertiary)
                Text(detail).font(.callout).foregroundStyle(.secondary)
            }
        }
        .fixedSize()
        .padding(.horizontal, 10).padding(.vertical, 4)
        .background(color(state).opacity(0.15), in: Capsule())
    }
}

/// Owns a `LogTail` and refreshes it; only the appended bytes are read on each poll.
@MainActor @Observable
final class LogModel {
    private(set) var lines: [String] = []
    @ObservationIgnored private var tail: LogTail

    init(url: URL) { tail = LogTail(url: url, maxLines: 300) }

    func poll() {
        if tail.poll() { lines = tail.lines }
    }
}

/// sync → prep → agent → check → merge as a stepper: filled dots for done, a ring for the current phase.
struct PhaseStrip: View {
    let steps: [PhaseStep]

    var body: some View {
        HStack(spacing: 0) {
            ForEach(Array(steps.enumerated()), id: \.element.name) { index, step in
                VStack(spacing: 6) {
                    ZStack {
                        Circle().fill(fill(step.state)).frame(width: 12, height: 12)
                        if step.state == .current {
                            Circle().stroke(Color.accentColor, lineWidth: 2).frame(width: 20, height: 20)
                        }
                    }
                    .frame(height: 20)
                    Text(step.name).font(.caption)
                        .foregroundStyle(step.state == .todo ? .secondary : .primary)
                }
                .frame(width: 56)
                if index < steps.count - 1 {
                    Rectangle().fill(step.state == .done ? Color.green.opacity(0.6) : Color.secondary.opacity(0.25))
                        .frame(height: 2).frame(maxWidth: .infinity).padding(.bottom, 18)
                }
            }
        }
        .padding(.horizontal, 8)
    }

    private func fill(_ state: PhaseStep.State) -> Color {
        switch state {
        case .done: return .green
        case .current: return .accentColor
        case .todo: return .secondary.opacity(0.3)
        }
    }
}

/// The log without idle ticks, newest at the bottom, scrolled there whenever something new lands.
/// The last idle check shows as one quiet line underneath, so it's still clear the loop is alive.
struct LogList: View {
    let all: [LogEntry]

    init(entries: [LogEntry]) { all = entries }

    private var entries: [LogEntry] { all.filter { $0.kind != "idle" } }
    private var lastIdle: LogEntry? { all.last.flatMap { $0.kind == "idle" ? $0 : nil } }

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            list
            if let idle = lastIdle {
                Text("Last checked \(idle.until ?? idle.time ?? ""): \(idle.text)")
                    .font(.caption).foregroundStyle(.tertiary)
            }
        }
    }

    @ViewBuilder private var list: some View {
        if entries.isEmpty {
            Text(all.isEmpty ? "No log yet." : "Nothing has happened yet.").foregroundStyle(.secondary)
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .background(.quaternary.opacity(0.4), in: RoundedRectangle(cornerRadius: 10))
        } else {
            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 0) {
                        ForEach(Array(entries.enumerated()), id: \.offset) { index, entry in
                            row(entry).id(index)
                        }
                    }
                    .padding(.vertical, 6)
                }
                .background(.quaternary.opacity(0.4), in: RoundedRectangle(cornerRadius: 10))
                .onAppear { proxy.scrollTo(entries.count - 1, anchor: .bottom) }
                .onChange(of: entries.count) { _, count in proxy.scrollTo(count - 1, anchor: .bottom) }
            }
        }
    }

    private func row(_ entry: LogEntry) -> some View {
        HStack(alignment: .firstTextBaseline, spacing: 10) {
            Text(entry.time ?? "").foregroundStyle(.secondary).frame(width: 40, alignment: .leading)
            if entry.time == nil {
                Text(entry.text).foregroundStyle(.secondary).padding(.leading, 16)
            } else if entry.kind.isEmpty {
                Text(entry.text).lineLimit(2)
            } else {
                Text(entry.kind).font(.system(size: 10, weight: .semibold, design: .monospaced))
                    .foregroundStyle(tint(entry.kind))
                    .padding(.horizontal, 6).padding(.vertical, 1)
                    .background(tint(entry.kind).opacity(0.15), in: Capsule())
                    .frame(width: 64, alignment: .leading)
                Text(entry.text).foregroundStyle(entry.kind == "idle" ? .secondary : .primary).lineLimit(2)
            }
            Spacer(minLength: 0)
        }
        .font(.system(size: 11, design: .monospaced))
        .textSelection(.enabled)
        .padding(.horizontal, 10).padding(.vertical, 3)
    }

    private func tint(_ kind: String) -> Color {
        switch kind {
        case "idle", "skip": return .secondary
        case "run", "prep", "sync": return .blue
        case "done", "answer": return .green
        case "review", "finish", "pr": return .purple
        case "fail", "park": return .red
        default: return .orange
        }
    }
}
