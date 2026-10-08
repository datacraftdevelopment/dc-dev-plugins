import AppKit
import SwiftUI
import RunwayCore

/// A narrow window to keep beside other work, read top to bottom as a timeline: what's queued (nearest just above),
/// what's running now, and what finished (newest just below). "Keep on top" floats it over other apps.
struct SidePanel: View {
    let store: ProjectStore
    @AppStorage("sidePanelOnTop") private var onTop = true
    @Environment(\.openWindow) private var openWindow
    @State private var finished = FinishedModel()

    var body: some View {
        TimelineView(.periodic(from: .now, by: 1)) { context in
            ScrollView {
                VStack(alignment: .leading, spacing: 10) {
                    if store.entries.isEmpty {
                        Text("No Runway projects found").foregroundStyle(.secondary)
                            .frame(maxWidth: .infinity).padding(.top, 40)
                    }
                    ForEach(store.entries) { entry in
                        ProjectNow(store: store, entry: entry, now: context.date) { route in
                            store.requestedRoute = route
                            NSApplication.shared.activate(ignoringOtherApps: true)
                            openWindow(id: "runway")
                        }
                    }
                    if !store.entries.isEmpty {
                        FinishedList(store: store, model: finished, now: context.date)
                    }
                }
                .padding(10)
            }
            .task(id: store.entries.map(\.id)) {
                while !Task.isCancelled {
                    await finished.reload(store.entries)
                    try? await Task.sleep(nanoseconds: 5 * 1_000_000_000)
                }
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
        // A fixed ideal height, so the window keeps its size when rows expand instead of growing with the list.
        .frame(minWidth: 260, idealWidth: 300, maxWidth: 380, minHeight: 240, idealHeight: 760, maxHeight: .infinity)
    }
}

// MARK: - up next and now

/// One project: its name, the queue above, and the current tick in a card.
private struct ProjectNow: View {
    let store: ProjectStore
    let entry: ProjectEntry
    let now: Date
    let open: (NotificationRoute) -> Void
    @State private var log: LogModel
    @State private var showAllQueued = false

    /// Queued tickets shown before the rest fold into "+N more".
    private static let queueShown = 4

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
        let snapshot = store.snapshot(for: project.label)
        let heartbeat = project.repoPath.flatMap { Heartbeat.load(repoPath: $0) }
        let live = heartbeat.flatMap { $0.isActive ? $0 : nil }
        let queued = (snapshot?.upNext ?? []).filter { $0.id != live?.ticket }

        VStack(alignment: .leading, spacing: 6) {
            header(snapshot: snapshot)
            if !queued.isEmpty { upNext(queued, snapshot: snapshot) }
            nowCard(heartbeat: heartbeat, live: live, snapshot: snapshot)
        }
        .contentShape(Rectangle())
        .onTapGesture(count: 2) { open(NotificationRoute(projectLabel: project.label, ticketID: nil, tab: .projects)) }
        .task(id: now) { log.poll() }
    }

    private func header(snapshot: StatusSnapshot?) -> some View {
        HStack(spacing: 6) {
            Circle().fill(color(entry.status.state)).frame(width: 8, height: 8)
            Text(entry.status.name).font(.headline).lineLimit(1)
            Spacer()
            if entry.status.waiting > 0 {
                Button { open(NotificationRoute(projectLabel: entry.project.label, ticketID: nil, tab: .decisions)) } label: {
                    Label("\(entry.status.waiting)", systemImage: "bell.fill").font(.caption.bold())
                }
                .buttonStyle(.borderless).foregroundStyle(.orange).help("Decisions waiting")
            }
            Text(entry.project.loaded ? (store.pause != nil ? "paused" : "loop on") : "loop off")
                .font(.caption).foregroundStyle(.secondary)
        }
        .padding(.horizontal, 2)
    }

    /// Nearest ticket at the bottom, next to Now; the far end folds into "+N more".
    private func upNext(_ queued: [StatusSnapshot.UpNext], snapshot: StatusSnapshot?) -> some View {
        let shown = showAllQueued ? queued : Array(queued.prefix(Self.queueShown))
        let hidden = queued.count - shown.count
        return VStack(alignment: .leading, spacing: 2) {
            SectionLabel(text: "Up next · \(queued.count)",
                         trailing: queued.contains { $0.kind == .prep } ? "some need prep" : nil)
            if hidden > 0 || showAllQueued && queued.count > Self.queueShown {
                Button { showAllQueued.toggle() } label: {
                    Text(showAllQueued ? "Show fewer" : "+\(hidden) more").font(.caption).foregroundStyle(.secondary)
                }
                .buttonStyle(.borderless).padding(.horizontal, 4)
            }
            ForEach(Array(shown.enumerated().reversed()), id: \.element.id) { index, ticket in
                QueueRow(ticket: ticket, isNext: index == 0, url: snapshot?.urls[ticket.id])
            }
        }
    }

    @ViewBuilder
    private func nowCard(heartbeat: Heartbeat?, live: Heartbeat?, snapshot: StatusSnapshot?) -> some View {
        if let live {
            let id = live.ticket ?? live.phase
            let title = live.ticket.flatMap { snapshot?.titles[$0] } ?? ""
            let events = LogFeed.entries(log.lines).filter { $0.kind != "idle" && $0.time != nil }.suffix(3)
            VStack(alignment: .leading, spacing: 8) {
                HStack(alignment: .firstTextBaseline) {
                    Text("\(id) · now").font(.caption.monospaced()).foregroundStyle(Color.accentColor)
                    Spacer()
                    Text(NowMath.elapsed(heartbeat: heartbeat, now: now).map(NowMath.clock) ?? "")
                        .font(.title3.monospacedDigit().weight(.medium))
                }
                if !title.isEmpty {
                    Text(title).font(.callout.weight(.medium)).lineLimit(3).fixedSize(horizontal: false, vertical: true)
                }
                NamedPhases(steps: NowMath.phaseStrip(heartbeat: heartbeat))
                Text(nowMeta(live)).font(.caption.monospacedDigit()).foregroundStyle(.secondary)
                if !events.isEmpty {
                    VStack(alignment: .leading, spacing: 2) {
                        ForEach(Array(events.enumerated()), id: \.offset) { _, event in
                            HStack(alignment: .firstTextBaseline, spacing: 6) {
                                Text(event.time ?? "").foregroundStyle(.tertiary)
                                Text(event.kind.isEmpty ? event.text : "\(event.kind) \(event.text)").lineLimit(1)
                                    .foregroundStyle(.secondary)
                            }
                        }
                    }
                    .font(.system(size: 10, design: .monospaced))
                }
                if let ticket = live.ticket, let url = snapshot?.urls[ticket] {
                    Link(destination: url) { Label("Linear", systemImage: "arrow.up.right.square") }.font(.caption)
                }
            }
            .padding(10)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Color.accentColor.opacity(0.08), in: RoundedRectangle(cornerRadius: 10))
            .overlay(RoundedRectangle(cornerRadius: 10).strokeBorder(Color.accentColor.opacity(0.6), lineWidth: 1))
        } else {
            let next = NowMath.nextTick(lastRun: heartbeat?.tickStarted ?? heartbeat?.since,
                                        interval: entry.project.interval, loopOn: entry.project.loaded, now: now)
            HStack(spacing: 6) {
                Image(systemName: entry.project.loaded ? "moon.zzz" : "pause.circle").foregroundStyle(.secondary)
                Text(entry.project.loaded ? "\(pillText(entry.status)) · next tick \(NowMath.text(next, now: now))"
                                          : pillText(entry.status))
                    .font(.caption.monospacedDigit()).foregroundStyle(.secondary).lineLimit(2)
            }
            .padding(10)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(.quaternary.opacity(0.5), in: RoundedRectangle(cornerRadius: 10))
        }
    }

    private func nowMeta(_ live: Heartbeat) -> String {
        let phase = live.since.map { "\(live.phase) \(NowMath.clock(now.timeIntervalSince($0)))" } ?? live.phase
        return [live.attempt.map { "attempt \($0)" }, phase].compactMap { $0 }.joined(separator: " · ")
    }
}

private struct QueueRow: View {
    let ticket: StatusSnapshot.UpNext
    let isNext: Bool
    let url: URL?

    var body: some View {
        HStack(spacing: 6) {
            Text(ticket.id).font(.system(size: 10, design: .monospaced)).foregroundStyle(.secondary)
            Text(ticket.title.isEmpty ? "—" : ticket.title).font(.caption).lineLimit(1)
                .foregroundStyle(isNext || ticket.kind == .ready ? .primary : .secondary)
            Spacer(minLength: 0)
            if ticket.kind == .prep { Pill(text: "prep", tint: .orange) }
            if isNext { Pill(text: "next", tint: .accentColor) }
        }
        .padding(.horizontal, 4).padding(.vertical, 1)
        .contentShape(Rectangle())
        .help(tooltip)
        .onTapGesture(count: 2) { if let url { NSWorkspace.shared.open(url) } }
    }

    private var tooltip: String {
        var lines = ["\(ticket.id) \(ticket.title)"]
        if ticket.kind == .prep { lines.append("Needs prep by a person before the loop takes it.") }
        if !ticket.blockedBy.isEmpty { lines.append("After " + ticket.blockedBy.joined(separator: ", ")) }
        if url != nil { lines.append("Double-click to open in Linear.") }
        return lines.joined(separator: "\n")
    }
}

/// The phase strip with each phase named under its bar.
private struct NamedPhases: View {
    let steps: [PhaseStep]

    var body: some View {
        HStack(spacing: 3) {
            ForEach(steps, id: \.name) { step in
                VStack(spacing: 2) {
                    Capsule().fill(fill(step.state)).frame(height: 4)
                    Text(step.name).font(.system(size: 9))
                        .foregroundStyle(step.state == .current ? Color.accentColor : .secondary)
                }
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

// MARK: - finished

/// A Finished row and the project it came from, so links and names resolve and rows from two repos stay distinct.
struct TaggedRow: Identifiable, Equatable {
    var id: String { "\(projectLabel)/\(row.id)" }
    let projectLabel: String
    let projectName: String
    let repo: String
    let row: FinishedRow
}

/// Reads each project's `_pm/runway-runs.jsonl` off the main actor, only when the file changed.
@MainActor @Observable
final class FinishedModel {
    private(set) var rows: [TaggedRow] = []
    private(set) var loaded = false
    @ObservationIgnored private var stamps: [String: Date] = [:]
    @ObservationIgnored private var perProject: [String: [TaggedRow]] = [:]

    func reload(_ entries: [ProjectEntry]) async {
        let targets = entries.compactMap { entry -> (String, String, String)? in
            entry.project.repoPath.map { (entry.project.label, entry.project.name, $0) }
        }
        var changed = Set(perProject.keys).subtracting(targets.map(\.0)).isEmpty == false
        perProject = perProject.filter { key, _ in targets.contains { $0.0 == key } }
        for (label, name, repo) in targets {
            let url = URL(fileURLWithPath: repo).appendingPathComponent("_pm/runway-runs.jsonl")
            let stamp = (try? FileManager.default.attributesOfItem(atPath: url.path)[.modificationDate]) as? Date
            guard stamp != stamps[label] || perProject[label] == nil else { continue }
            stamps[label] = stamp
            let parsed = await Task.detached { (try? Data(contentsOf: url)).map { PanelHistory.rows($0) } ?? [] }.value
            perProject[label] = parsed.map { TaggedRow(projectLabel: label, projectName: name, repo: repo, row: $0) }
            changed = true
        }
        loaded = true
        guard changed else { return }
        rows = perProject.values.flatMap { $0 }
            .sorted { ($0.row.finishedAt ?? .distantPast) > ($1.row.finishedAt ?? .distantPast) }
    }
}

private struct FinishedList: View {
    let store: ProjectStore
    let model: FinishedModel
    let now: Date
    @State private var expanded: Set<String> = []

    var body: some View {
        let days = PanelHistory.days(model.rows, date: \.row.finishedAt, now: now)
        let multiProject = Set(model.rows.map(\.projectLabel)).count > 1
        VStack(alignment: .leading, spacing: 2) {
            SectionLabel(text: "Finished", trailing: nil)
            if model.loaded && days.isEmpty {
                Text("Nothing finished yet.").font(.caption).foregroundStyle(.secondary).padding(.horizontal, 4)
            }
            ForEach(days) { day in
                let rows = day.rows.map(\.row)
                SectionLabel(text: day.label,
                             trailing: "\(PanelHistory.doneCount(rows)) done · \(PanelHistory.cost(PanelHistory.cost(of: rows)))")
                    .padding(.top, 4)
                ForEach(day.rows) { tagged in
                    FinishedRowView(tagged: tagged, snapshot: store.snapshot(for: tagged.projectLabel),
                                    showProject: multiProject, isExpanded: expanded.contains(tagged.id)) {
                        if expanded.contains(tagged.id) { expanded.remove(tagged.id) } else { expanded.insert(tagged.id) }
                    }
                }
            }
        }
    }
}

private struct FinishedRowView: View {
    let tagged: TaggedRow
    let snapshot: StatusSnapshot?
    let showProject: Bool
    let isExpanded: Bool
    let toggle: () -> Void
    @State private var message: String?

    var body: some View {
        VStack(alignment: .leading, spacing: 3) {
            Button(action: toggle) { summary.contentShape(Rectangle()) }
                .buttonStyle(.plain)
                .accessibilityHint(isExpanded ? "Hide details" : "Show details")
            if isExpanded {
                details
                    .padding(8)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(.quaternary.opacity(0.5), in: RoundedRectangle(cornerRadius: 6))
                    .padding(.leading, 20).padding(.top, 2)
            }
        }
        .padding(.horizontal, 4).padding(.vertical, 4)
        .overlay(alignment: .top) { Divider().opacity(0.5) }
    }

    // MARK: summary

    @ViewBuilder private var summary: some View {
        switch tagged.row {
        case .ticket(let t):
            line(icon: icon(t), id: t.ticket, idTint: .secondary, title: snapshot?.titles[t.ticket] ?? "",
                 pill: t.attempts > 1 ? ("\(t.attempts) tries", .orange) : nil,
                 meta: [t.wallSecs.map(PanelHistory.duration), PanelHistory.cost(t.costUSD), clock(t.finishedAt),
                        t.result == "done" ? nil : resultText(t.result)])
        case .noWork(let group):
            line(icon: ("exclamationmark.triangle.fill", .orange),
                 id: group.count == 1 ? group[0].ticket : "\(group.count) tickets", idTint: .orange,
                 title: "marked done, agent never ran", pill: nil,
                 meta: [timeSpan(group), exitText(group), "$0"])
        case .finish(let f):
            line(icon: ("arrow.triangle.pull", .purple), id: "Finish", idTint: .purple,
                 title: f.checkPassed == false ? "integration check failed" : "integration ready for review", pill: nil,
                 meta: [clock(f.finishedAt), f.findings.map { $0 ? "review findings" : "review clean" },
                        f.costUSD > 0 ? PanelHistory.cost(f.costUSD) : nil])
        }
    }

    private func line(icon: (String, Color), id: String, idTint: Color, title: String, pill: (String, Color)?,
                      meta: [String?]) -> some View {
        VStack(alignment: .leading, spacing: 1) {
            HStack(spacing: 6) {
                Image(systemName: icon.0).foregroundStyle(icon.1).font(.system(size: 12)).frame(width: 14)
                Text(id).font(.system(size: 10, design: .monospaced)).foregroundStyle(idTint)
                Text(title.isEmpty ? "—" : title).font(.caption).lineLimit(1)
                Spacer(minLength: 0)
                if let pill { Pill(text: pill.0, tint: pill.1) }
            }
            Text(((showProject ? [tagged.projectName] : []) + meta.compactMap { $0 }).joined(separator: " · "))
                .font(.caption2.monospacedDigit()).foregroundStyle(.secondary)
                .padding(.leading, 20)
        }
        .help(title.isEmpty ? id : "\(id) \(title)")
    }

    // MARK: details

    @ViewBuilder private var details: some View {
        switch tagged.row {
        case .ticket(let t): ticketDetails(t)
        case .noWork(let group): noWorkDetails(group)
        case .finish(let f): finishDetails(f)
        }
    }

    private func ticketDetails(_ t: FinishedTicket) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            VStack(alignment: .leading, spacing: 2) {
                ForEach(t.steps) { step in
                    HStack(spacing: 8) {
                        Text("#\(step.attempt ?? 0)").foregroundStyle(.secondary)
                        if step.kind != "run" { Text(step.kind) }
                        Text(step.secs.map(NowMath.clock) ?? "—")
                        Text(step.costUSD.map(PanelHistory.cost) ?? "—")
                        Text(exitLabel(step)).foregroundStyle(step.result == .fail ? .red : .secondary)
                        Spacer(minLength: 0)
                        if let id = step.sessionID, !id.isEmpty {
                            Button { openSession(id) } label: { Image(systemName: "doc.text.magnifyingglass") }
                                .buttonStyle(.borderless).help("Show this call's session transcript in Finder")
                        }
                    }
                    .lineLimit(1).fixedSize(horizontal: false, vertical: true)
                }
            }
            .font(.system(size: 10, design: .monospaced))
            Text("\(PanelHistory.tokens(t.tokens)) tokens · \(t.turns) turns · agent \(NowMath.clock(t.agentSecs))"
                 + (t.result == "done" ? "" : " · \(resultText(t.result))"))
                .font(.caption2).foregroundStyle(.secondary)
            if !t.detail.isEmpty {
                ScrollView {
                    Text(t.detail.replacingOccurrences(of: "```", with: "").trimmingCharacters(in: .whitespacesAndNewlines))
                        .font(.system(size: 10, design: .monospaced)).textSelection(.enabled)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
                .frame(maxHeight: 120)
            }
            if let message { Text(message).font(.caption2).foregroundStyle(.red) }
            if let url = snapshot?.urls[t.ticket] {
                Link(destination: url) { Label("Linear", systemImage: "arrow.up.right.square") }.font(.caption)
            }
        }
    }

    private func noWorkDetails(_ group: [FinishedTicket]) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            ForEach(group) { t in
                HStack(spacing: 6) {
                    Text(t.ticket).font(.system(size: 10, design: .monospaced))
                    Text(snapshot?.titles[t.ticket] ?? "").font(.caption2).lineLimit(1).foregroundStyle(.secondary)
                    Spacer(minLength: 0)
                    Text(clock(t.finishedAt) ?? "").font(.caption2.monospacedDigit()).foregroundStyle(.secondary)
                }
            }
            Text("Logged as done, but every agent call used no tokens.")
                .font(.caption2).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
        }
    }

    private func finishDetails(_ f: FinishRecord) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            if !f.fix.isEmpty {
                Text(f.fix).font(.caption2).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
            }
            if !f.pr.isEmpty {
                Button { openPR(f.pr) } label: { Label("Open PR draft", systemImage: "doc.text") }
                    .buttonStyle(.link).font(.caption)
            }
            if let message { Text(message).font(.caption2).foregroundStyle(.red) }
        }
    }

    // MARK: helpers

    private func icon(_ t: FinishedTicket) -> (String, Color) {
        switch t.result {
        case "done": return ("checkmark.circle.fill", .green)
        case "needs-human": return ("hand.raised.fill", .orange)
        case "stopped": return ("stop.circle.fill", .secondary)
        default: return ("questionmark.circle", .secondary)
        }
    }

    private func resultText(_ result: String) -> String {
        switch result {
        case "needs-human": return "needs you"
        case "stopped": return "stopped"
        default: return result
        }
    }

    private func exitLabel(_ step: RunRecord) -> String {
        step.details.first { $0.key == "exit" }.map { "exit \($0.value)" } ?? ""
    }

    private func exitText(_ group: [FinishedTicket]) -> String? {
        let exits = Set(group.flatMap(\.steps).compactMap { step in step.details.first { $0.key == "exit" }?.value })
        return exits.isEmpty ? nil : "exit " + exits.sorted().joined(separator: "/")
    }

    private func clock(_ date: Date?) -> String? {
        guard let date else { return nil }
        let formatter = DateFormatter()
        formatter.dateFormat = "HH:mm"
        return formatter.string(from: date)
    }

    private func timeSpan(_ group: [FinishedTicket]) -> String? {
        let times = group.compactMap { clock($0.finishedAt) }
        guard let newest = times.first, let oldest = times.last else { return nil }
        return newest == oldest ? newest : "\(oldest)–\(newest)"
    }

    private func openSession(_ id: String) {
        let projects = FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent(".claude/projects")
        if let url = RunsLog.transcript(sessionID: id, projectsDir: projects) {
            NSWorkspace.shared.activateFileViewerSelecting([url])
            message = nil
        } else {
            message = "No transcript found for session \(id)."
        }
    }

    private func openPR(_ path: String) {
        let url = path.hasPrefix("/") ? URL(fileURLWithPath: path) : URL(fileURLWithPath: tagged.repo).appendingPathComponent(path)
        if FileManager.default.fileExists(atPath: url.path) {
            NSWorkspace.shared.open(url)
            message = nil
        } else {
            message = "\(path) isn't there any more."
        }
    }
}

// MARK: - small pieces

private struct SectionLabel: View {
    let text: String
    let trailing: String?

    var body: some View {
        HStack {
            Text(text)
            Spacer()
            if let trailing { Text(trailing) }
        }
        .font(.caption2).foregroundStyle(.secondary).padding(.horizontal, 4).padding(.top, 2)
    }
}

private struct Pill: View {
    let text: String
    let tint: Color

    var body: some View {
        Text(text).font(.system(size: 9, weight: .medium)).padding(.horizontal, 5).padding(.vertical, 1)
            .foregroundStyle(tint).background(tint.opacity(0.15), in: Capsule())
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
