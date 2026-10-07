import SwiftUI
import RunwayCore

enum RunwayTab: String, CaseIterable, Identifiable {
    case now = "Now", queue = "Queue", decisions = "Decisions", runs = "Runs"
    var id: String { rawValue }
}

struct RunwayWindow: View {
    let store: ProjectStore
    @State private var selection: String?
    @State private var tab: RunwayTab = .now

    private var entry: ProjectEntry? {
        store.entries.first { $0.project.label == selection } ?? store.entries.first
    }

    var body: some View {
        NavigationSplitView {
            List(store.entries, selection: $selection) { entry in
                HStack {
                    Circle().fill(color(entry.status.state)).frame(width: 9, height: 9)
                    Text(entry.status.name)
                    Spacer()
                    if entry.status.waiting > 0 {
                        Text("\(entry.status.waiting)")
                            .font(.caption.bold()).foregroundStyle(.white)
                            .padding(.horizontal, 6).background(.orange, in: Capsule())
                    }
                }
                .tag(entry.project.label)
            }
            .navigationSplitViewColumnWidth(min: 180, ideal: 210)
        } detail: {
            if let entry {
                VStack(spacing: 0) {
                    Picker("", selection: $tab) {
                        ForEach(RunwayTab.allCases) { Text($0.rawValue).tag($0) }
                    }
                    .pickerStyle(.segmented).labelsHidden().padding(10)
                    Divider()
                    if tab == .now {
                        NowTab(store: store, entry: entry).id(entry.project.label)
                    } else if tab == .queue {
                        QueueTab(store: store, entry: entry)
                    } else {
                        Text("\(tab.rawValue): coming soon")
                            .foregroundStyle(.secondary).frame(maxWidth: .infinity, maxHeight: .infinity)
                    }
                }
                .toolbar { toolbar(for: entry) }
                .navigationTitle(entry.status.name)
            } else {
                Text("No Runway projects found").foregroundStyle(.secondary)
            }
        }
        .frame(minWidth: 760, minHeight: 480)
        .onChange(of: store.requestedRoute) { _, route in
            guard let route else { return }
            selection = route.projectLabel
            tab = route.tab == .decisions ? .decisions : .now
            store.requestedRoute = nil
        }
    }

    @ToolbarContentBuilder private func toolbar(for entry: ProjectEntry) -> some ToolbarContent {
        let project = entry.project
        ToolbarItemGroup {
            StatePill(state: entry.status.state, text: pillText(entry.status))
            Text(project.interval.map { "every \(max(1, $0 / 60))m" } ?? "no interval")
                .font(.caption).foregroundStyle(.secondary)
            if project.loaded {
                Button("Stop") { Task { await store.stopLoop(project) } }
            } else {
                Button("Start") { Task { await store.startLoop(project) } }
                    .disabled(project.repoPath == nil || project.error != nil)
            }
            Button("Run a tick now") { Task { await store.runNow(project) } }
                .disabled(!project.loaded)
        }
    }

    private func pillText(_ status: ProjectStatus) -> String {
        switch status.state {
        case .running: return "Running"
        case .waiting: return "Waiting on you"
        case .paused: return "Paused"
        case .idle: return "Idle"
        case .off: return "Off"
        case .error: return "Error"
        }
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

    var body: some View {
        Text(text).font(.caption.bold()).foregroundStyle(.white)
            .padding(.horizontal, 8).padding(.vertical, 2)
            .background(color(state), in: Capsule())
    }
}

/// Owns a `LogTail` and refreshes it; only the appended bytes are read on each poll.
@MainActor @Observable
final class LogModel {
    private(set) var lines: [String] = []
    @ObservationIgnored private var tail: LogTail

    init(url: URL) { tail = LogTail(url: url, maxLines: 30) }

    func poll() {
        if tail.poll() { lines = tail.lines }
    }
}

struct NowTab: View {
    let store: ProjectStore
    let entry: ProjectEntry
    @State private var log: LogModel

    init(store: ProjectStore, entry: ProjectEntry) {
        self.store = store
        self.entry = entry
        let repo = entry.project.repoPath ?? ""
        _log = State(initialValue: LogModel(url: URL(fileURLWithPath: repo).appendingPathComponent("_pm/runway.log")))
    }

    var body: some View {
        // One second is enough for the elapsed clock and the log; the log read itself is incremental.
        TimelineView(.periodic(from: .now, by: 1)) { context in
            content(now: context.date)
                .task(id: context.date) { log.poll() }
        }
    }

    @ViewBuilder private func content(now: Date) -> some View {
        let project = entry.project
        let heartbeat = project.repoPath.flatMap { Heartbeat.load(repoPath: $0) }
        let snapshot = store.snapshot(for: project.label)
        let banners = NowMath.banners(loopOn: project.loaded, readyCount: snapshot?.readyCount ?? 0,
                                      waiting: entry.status.waiting, paused: store.pause != nil)
        let live = heartbeat.flatMap { $0.isActive ? $0 : nil }
        let next = NowMath.nextTick(lastRun: heartbeat?.tickStarted ?? heartbeat?.since, interval: project.interval,
                                    loopOn: project.loaded, now: now)

        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                ForEach(Array(banners.enumerated()), id: \.offset) { _, banner in
                    Text(bannerText(banner)).padding(10).frame(maxWidth: .infinity, alignment: .leading)
                        .background(.orange.opacity(0.2), in: RoundedRectangle(cornerRadius: 8))
                }
                HStack(alignment: .top, spacing: 12) {
                    cell("Working on", live?.ticket.map { id in
                        let title = snapshot?.titles[id] ?? ""
                        return title.isEmpty ? id : "\(id) \(title)"
                    } ?? "Nothing right now")
                    cell("Elapsed · attempt", NowMath.elapsed(heartbeat: heartbeat, now: now).map {
                        NowMath.clock($0) + (live?.attempt.map { " · #\($0)" } ?? "")
                    } ?? "—")
                    cell("Next tick", NowMath.text(next, now: now))
                }
                HStack(spacing: 6) {
                    ForEach(NowMath.phaseStrip(heartbeat: heartbeat), id: \.name) { step in
                        Text(step.name).font(.caption)
                            .frame(maxWidth: .infinity).padding(.vertical, 6)
                            .background(stepColor(step.state), in: RoundedRectangle(cornerRadius: 6))
                    }
                }
                Text("_pm/runway.log").font(.caption).foregroundStyle(.secondary)
                Text(log.lines.isEmpty ? "No log yet." : log.lines.joined(separator: "\n"))
                    .font(.system(size: 11, design: .monospaced)).textSelection(.enabled)
                    .frame(maxWidth: .infinity, alignment: .leading).padding(8)
                    .background(.black.opacity(0.06), in: RoundedRectangle(cornerRadius: 6))
            }
            .padding(14)
        }
    }

    private func cell(_ title: String, _ value: String) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(title).font(.caption).foregroundStyle(.secondary)
            Text(value).font(.body.monospacedDigit()).lineLimit(2)
        }
        .padding(10).frame(maxWidth: .infinity, alignment: .leading)
        .background(.quaternary, in: RoundedRectangle(cornerRadius: 8))
    }

    private func stepColor(_ state: PhaseStep.State) -> Color {
        switch state {
        case .done: return .green.opacity(0.35)
        case .current: return .accentColor.opacity(0.6)
        case .todo: return .gray.opacity(0.15)
        }
    }

    private func bannerText(_ banner: NowBanner) -> String {
        switch banner {
        case .loopOffReady(let n): return "Loop is off with \(n) ticket\(n == 1 ? "" : "s") ready. Start it to pick them up."
        case .decisionsWaiting(let n): return "\(n) decision\(n == 1 ? "" : "s") waiting on you."
        case .paused: return "All loops are paused."
        }
    }
}
