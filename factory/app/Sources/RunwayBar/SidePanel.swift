import AppKit
import SwiftUI
import RunwayCore

/// A narrow window to keep beside other work: every project's state, what it's on, the phase it's in,
/// and its last few real events. "Keep on top" floats it over other apps.
struct SidePanel: View {
    let store: ProjectStore
    @AppStorage("sidePanelOnTop") private var onTop = true
    @Environment(\.openWindow) private var openWindow

    var body: some View {
        TimelineView(.periodic(from: .now, by: 1)) { context in
            ScrollView {
                VStack(spacing: 10) {
                    if store.entries.isEmpty {
                        Text("No Runway projects found").foregroundStyle(.secondary).padding(.top, 40)
                    }
                    ForEach(store.entries) { entry in
                        SidePanelCard(store: store, entry: entry, now: context.date) { route in
                            store.requestedRoute = route
                            NSApplication.shared.activate(ignoringOtherApps: true)
                            openWindow(id: "runway")
                        }
                    }
                }
                .padding(10)
            }
        }
        .safeAreaInset(edge: .bottom) {
            HStack {
                Toggle("Keep on top", isOn: $onTop).toggleStyle(.checkbox).font(.caption)
                Spacer()
                Button {
                    NSApplication.shared.activate(ignoringOtherApps: true)
                    openWindow(id: "runway")
                } label: { Label("Full window", systemImage: "macwindow") }
                .buttonStyle(.borderless).font(.caption)
            }
            .padding(.horizontal, 12).padding(.vertical, 8)
            .background(.bar)
        }
        .background(WindowLevel(floating: onTop))
        .frame(minWidth: 240, idealWidth: 280, maxWidth: 360, minHeight: 200)
    }
}

private struct SidePanelCard: View {
    let store: ProjectStore
    let entry: ProjectEntry
    let now: Date
    let open: (NotificationRoute) -> Void
    @State private var log: LogModel

    init(store: ProjectStore, entry: ProjectEntry, now: Date, open: @escaping (NotificationRoute) -> Void) {
        self.store = store
        self.entry = entry
        self.now = now
        self.open = open
        let repo = entry.project.repoPath ?? ""
        _log = State(initialValue: LogModel(url: URL(fileURLWithPath: repo).appendingPathComponent("_pm/runway.log")))
    }

    var body: some View {
        let project = entry.project
        let heartbeat = project.repoPath.flatMap { Heartbeat.load(repoPath: $0) }
        let live = heartbeat.flatMap { $0.isActive ? $0 : nil }
        let snapshot = store.snapshot(for: project.label)
        let next = NowMath.nextTick(lastRun: heartbeat?.tickStarted ?? heartbeat?.since, interval: project.interval,
                                    loopOn: project.loaded, now: now)
        let events = LogFeed.entries(log.lines).filter { $0.kind != "idle" && $0.time != nil }.suffix(3)

        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 6) {
                Circle().fill(color(entry.status.state)).frame(width: 8, height: 8)
                Text(entry.status.name).font(.headline).lineLimit(1)
                Spacer()
                if entry.status.waiting > 0 {
                    Button { open(NotificationRoute(projectLabel: project.label, ticketID: nil, tab: .decisions)) } label: {
                        Label("\(entry.status.waiting)", systemImage: "bell.fill").font(.caption.bold())
                    }
                    .buttonStyle(.borderless).foregroundStyle(.orange).help("Decisions waiting")
                }
            }
            if let live {
                let id = live.ticket ?? live.phase
                let title = live.ticket.flatMap { snapshot?.titles[$0] } ?? ""
                VStack(alignment: .leading, spacing: 2) {
                    Text(title.isEmpty ? id : "\(id) \(title)").font(.callout).lineLimit(2)
                    Text([NowMath.elapsed(heartbeat: heartbeat, now: now).map(NowMath.clock),
                          live.attempt.map { "attempt \($0)" }].compactMap { $0 }.joined(separator: " · "))
                        .font(.caption.monospacedDigit()).foregroundStyle(.secondary)
                }
                MiniPhases(steps: NowMath.phaseStrip(heartbeat: heartbeat))
            } else {
                Text(project.loaded ? "\(pillText(entry.status)) · next tick \(NowMath.text(next, now: now))"
                                    : pillText(entry.status))
                    .font(.caption.monospacedDigit()).foregroundStyle(.secondary)
            }
            if !events.isEmpty {
                VStack(alignment: .leading, spacing: 3) {
                    ForEach(Array(events.enumerated()), id: \.offset) { _, event in
                        HStack(alignment: .firstTextBaseline, spacing: 6) {
                            Text(event.time ?? "").foregroundStyle(.tertiary)
                            Text(event.kind.isEmpty ? event.text : "\(event.kind) \(event.text)").lineLimit(1)
                                .foregroundStyle(.secondary)
                        }
                        .font(.system(size: 10, design: .monospaced))
                    }
                }
            }
        }
        .padding(10)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(.quaternary.opacity(0.5), in: RoundedRectangle(cornerRadius: 10))
        .contentShape(Rectangle())
        .onTapGesture(count: 2) { open(NotificationRoute(projectLabel: project.label, ticketID: nil, tab: .projects)) }
        .task(id: now) { log.poll() }
    }
}

/// The phase strip shrunk to a row of dots with the current phase named.
private struct MiniPhases: View {
    let steps: [PhaseStep]

    var body: some View {
        HStack(spacing: 4) {
            ForEach(steps, id: \.name) { step in
                Capsule().fill(fill(step.state)).frame(height: 4)
            }
            if let current = steps.first(where: { $0.state == .current }) {
                Text(current.name).font(.caption2).foregroundStyle(Color.accentColor).fixedSize()
            }
        }
    }

    private func fill(_ state: PhaseStep.State) -> Color {
        switch state {
        case .done: return .green
        case .current: return .accentColor
        case .todo: return .secondary.opacity(0.25)
        }
    }
}

/// Sets the hosting window's level, so the panel can float above other apps.
private struct WindowLevel: NSViewRepresentable {
    let floating: Bool

    func makeNSView(context: Context) -> NSView { NSView() }

    func updateNSView(_ view: NSView, context: Context) {
        DispatchQueue.main.async {
            view.window?.level = floating ? .floating : .normal
            view.window?.collectionBehavior.insert(.canJoinAllSpaces)
        }
    }
}
