import AppKit
import SwiftUI
import RunwayCore

/// The window's main view: today's numbers, the ticket board (Blocked, Needs you, Up next, Running, Done this round),
/// a details pane for the clicked card, and the activity log as a drawer. Columns come from `Board.build`.
struct BoardTab: View {
    let store: ProjectStore
    let entry: ProjectEntry
    @Binding var selected: String?
    @State private var feed = DecisionsFeed()
    @State private var runs: [RunRecord] = []
    @State private var log: LogModel
    @AppStorage("boardLogOpen") private var logOpen = false

    init(store: ProjectStore, entry: ProjectEntry, selected: Binding<String?>) {
        self.store = store
        self.entry = entry
        _selected = selected
        let repo = entry.project.repoPath ?? ""
        _log = State(initialValue: LogModel(url: URL(fileURLWithPath: repo).appendingPathComponent("_pm/runway.log")))
    }

    private var statusCommand: Command? {
        guard let repo = entry.project.repoPath, let tools = store.tools else { return nil }
        return tools.status(repo: repo)
    }

    var body: some View {
        TimelineView(.periodic(from: .now, by: 1)) { context in
            content(now: context.date)
                .task(id: context.date) { log.poll() }
        }
        // Status calls the tracker, so once a minute; the runs log is a local file, so every 10 seconds.
        .task(id: entry.project.label) {
            while !Task.isCancelled {
                if let command = statusCommand { await feed.refresh(command) }
                try? await Task.sleep(nanoseconds: 60 * 1_000_000_000)
            }
        }
        .task(id: entry.project.label) {
            while !Task.isCancelled {
                await reloadRuns()
                try? await Task.sleep(nanoseconds: 10 * 1_000_000_000)
            }
        }
    }

    private func reloadRuns() async {
        guard let repo = entry.project.repoPath else { return }
        let url = URL(fileURLWithPath: repo)
        runs = await Task.detached { RunsSnapshot.load(repo: url).records }.value
    }

    @ViewBuilder private func content(now: Date) -> some View {
        let project = entry.project
        let heartbeat = project.repoPath.flatMap { Heartbeat.load(repoPath: $0) }
        let live = store.live(heartbeat)
        let board = Board.build(queue: feed.queue, liveTicket: live?.ticket, runs: runs)
        let stats = BoardStats.make(board: board, runs: runs, now: now)
        let next = NowMath.nextTick(lastRun: heartbeat?.tickStarted ?? heartbeat?.since, interval: project.interval,
                                    loopOn: project.loaded, now: now)

        VStack(spacing: 0) {
            VStack(alignment: .leading, spacing: 10) {
                if case .error = entry.status.state { ErrorBanner(store: store, entry: entry, lines: log.lines) }
                if let error = feed.error {
                    Text(feed.queue == nil ? error : "\(error) Showing the last good result.")
                        .font(.caption).textSelection(.enabled).padding(8).frame(maxWidth: .infinity, alignment: .leading)
                        .background(.red.opacity(0.15), in: RoundedRectangle(cornerRadius: 6))
                }
                if store.pause != nil {
                    Label("All loops are paused.", systemImage: "pause.circle.fill")
                        .padding(8).frame(maxWidth: .infinity, alignment: .leading)
                        .background(.yellow.opacity(0.15), in: RoundedRectangle(cornerRadius: 8))
                }
                statsStrip(stats, next: NowMath.text(next, now: now))
            }
            .padding(.horizontal, 16).padding(.top, 12).padding(.bottom, 8)

            HStack(spacing: 0) {
                ScrollView(.horizontal) {
                    HStack(alignment: .top, spacing: 12) {
                        column(.blocked, board, width: 200)
                        column(.needsYou, board, width: 230)
                        column(.upNext, board, width: 230)
                        RunningColumn(store: store, entry: entry, board: board, heartbeat: heartbeat, live: live,
                                      log: log.lines, next: NowMath.text(next, now: now), now: now, selected: $selected)
                        column(.done, board, width: 230)
                    }
                    .padding(.horizontal, 16).padding(.vertical, 8)
                    .frame(maxHeight: .infinity, alignment: .top)
                }
                if let card = board.card(selected) {
                    Divider()
                    CardDetails(store: store, entry: entry, card: card, feed: feed, runs: runs,
                                statusCommand: statusCommand) { selected = nil }
                        .frame(width: 340)
                        .id(card.id)
                }
            }
            .frame(maxHeight: .infinity)

            Divider()
            ActivityDrawer(entries: LogFeed.entries(log.lines), repo: project.repoPath, open: $logOpen)
        }
    }

    private func statsStrip(_ stats: BoardStats, next: String) -> some View {
        HStack(spacing: 10) {
            stat("Merged this round", "\(stats.mergedThisRound)", "into the integration branch")
            stat("Spend today", String(format: "$%.2f", stats.spendToday), "\(BoardStats.tokens(stats.tokensToday)) tokens")
            stat("Needs you", "\(stats.needsYou)", stats.needsYou == 0 ? "nothing waiting" : "decisions and errors")
            stat("Next tick", next, "every \(max(1, (entry.project.interval ?? 600) / 60)) min")
        }
    }

    private func stat(_ label: String, _ value: String, _ sub: String) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(label.uppercased()).font(.caption2.weight(.semibold)).foregroundStyle(.secondary)
            Text(value).font(.title2.weight(.semibold).monospacedDigit()).lineLimit(1)
            Text(sub).font(.caption).foregroundStyle(.secondary).lineLimit(1)
        }
        .padding(.horizontal, 12).padding(.vertical, 8)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(.quaternary.opacity(0.5), in: RoundedRectangle(cornerRadius: 10))
    }

    private func column(_ column: BoardColumn, _ board: Board, width: CGFloat) -> some View {
        let cards = board.cards(column)
        return VStack(alignment: .leading, spacing: 8) {
            ColumnHeader(column: column, count: cards.count)
            ScrollView {
                LazyVStack(spacing: 8) {
                    if cards.isEmpty {
                        Text(emptyText(column)).font(.caption).foregroundStyle(.tertiary)
                            .frame(maxWidth: .infinity, alignment: .leading).padding(.horizontal, 4)
                    }
                    ForEach(cards) { card in
                        CardView(card: card, selected: selected == card.id) {
                            selected = selected == card.id ? nil : card.id
                        }
                    }
                }
            }
            if column == .done {
                Divider()
                VStack(alignment: .leading, spacing: 2) {
                    Text("Finish").font(.caption.weight(.semibold))
                    Text("Runs when the queue is empty: review, one fix pass, re-test, draft PR.")
                        .font(.caption).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
                }
                .padding(.horizontal, 4)
            }
        }
        .padding(10)
        .frame(width: width, alignment: .top)
        .frame(maxHeight: .infinity, alignment: .top)
        .background(columnTint(column).opacity(0.07), in: RoundedRectangle(cornerRadius: 12))
        .overlay(RoundedRectangle(cornerRadius: 12).strokeBorder(.quaternary, lineWidth: 1))
    }

    private func emptyText(_ column: BoardColumn) -> String {
        switch column {
        case .blocked: return "Nothing blocked"
        case .needsYou: return "Nothing waiting on you"
        case .upNext: return "Queue is empty"
        case .running: return ""
        case .done: return "Nothing merged yet this round"
        }
    }
}

func columnTint(_ column: BoardColumn) -> Color {
    switch column {
    case .blocked: return .gray
    case .needsYou: return .orange
    case .upNext: return .secondary
    case .running: return .blue
    case .done: return .green
    }
}

private struct ColumnHeader: View {
    let column: BoardColumn
    let count: Int

    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            HStack(spacing: 6) {
                Circle().fill(columnTint(column)).frame(width: 8, height: 8)
                Text(column.title).font(.headline)
                Text("\(count)").font(.callout).foregroundStyle(.secondary)
            }
            if !column.hint.isEmpty {
                Text(column.hint).font(.caption).foregroundStyle(.secondary)
            }
        }
        .padding(.horizontal, 4)
    }
}

/// One ticket. A click selects it (and a second click deselects); the details pane does the rest.
private struct CardView: View {
    let card: BoardCard
    let selected: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            VStack(alignment: .leading, spacing: 5) {
                HStack(spacing: 6) {
                    Text(card.id).font(.caption.monospaced()).foregroundStyle(.secondary)
                    Spacer(minLength: 4)
                    if let errored = card.errored { ErroredFlag(kind: errored, compact: true) }
                    if card.waiting { chip("decision", .orange) }
                    if card.needsPrep { chip("prep", .gray) }
                    if let harness = card.harness, harness != "claude" { chip(harness, .purple) }
                }
                Text(card.title.isEmpty ? card.id : card.title).font(.callout.weight(.medium))
                    .multilineTextAlignment(.leading).lineLimit(3)
                if let note = card.note {
                    Text(note).font(.caption).foregroundStyle(.secondary).lineLimit(2)
                }
            }
            .padding(10)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(.background.opacity(0.6), in: RoundedRectangle(cornerRadius: 9))
            .overlay(RoundedRectangle(cornerRadius: 9)
                .strokeBorder(selected ? Color.accentColor : Color.secondary.opacity(0.2), lineWidth: selected ? 2 : 1))
            .contentShape(RoundedRectangle(cornerRadius: 9))
        }
        .buttonStyle(.plain)
        .help("Show details")
    }
}

func chip(_ text: String, _ color: Color) -> some View {
    Text(text).font(.caption2.bold()).padding(.horizontal, 6).padding(.vertical, 1)
        .background(color.opacity(0.2), in: Capsule())
}

/// The ticket in flight, big: elapsed, attempt, the phase strip and the latest log lines.
/// With the loop off it says so and offers Start; between tickets it shows the next tick.
private struct RunningColumn: View {
    let store: ProjectStore
    let entry: ProjectEntry
    let board: Board
    let heartbeat: Heartbeat?
    let live: Heartbeat?
    let log: [String]
    let next: String
    let now: Date
    @Binding var selected: String?

    var body: some View {
        let cards = board.cards(.running)
        VStack(alignment: .leading, spacing: 10) {
            ColumnHeader(column: .running, count: cards.count)
            if let stopped = store.stoppedLine(heartbeat) {
                Label([heartbeat?.ticket, stopped].compactMap { $0 }.joined(separator: " · "),
                      systemImage: "exclamationmark.octagon.fill")
                    .font(.caption).foregroundStyle(.red)
                    .padding(8).frame(maxWidth: .infinity, alignment: .leading)
                    .background(.red.opacity(0.1), in: RoundedRectangle(cornerRadius: 8))
            }
            if let card = cards.first {
                hero(card)
                ForEach(cards.dropFirst()) { other in
                    CardView(card: other, selected: selected == other.id) { selected = other.id }
                }
            } else if !entry.project.loaded {
                VStack(alignment: .leading, spacing: 8) {
                    Text("Loop is off").font(.headline)
                    let ready = board.cards(.upNext).count
                    Text(ready == 0 ? "Start it to run tickets as they become ready."
                         : "\(ready) ticket\(ready == 1 ? " is" : "s are") ready. Start the loop to pick \(ready == 1 ? "it" : "them") up.")
                        .font(.caption).foregroundStyle(.secondary)
                    Button { Task { await store.startLoop(entry.project) } } label: { Label("Start", systemImage: "play.fill") }
                        .disabled(entry.project.repoPath == nil || entry.project.error != nil)
                }
                .padding(12).frame(maxWidth: .infinity, alignment: .leading)
                .overlay(RoundedRectangle(cornerRadius: 10).strokeBorder(style: StrokeStyle(lineWidth: 1, dash: [4])).foregroundStyle(.blue.opacity(0.5)))
            } else {
                Text("Nothing running right now.").font(.callout).foregroundStyle(.secondary)
            }
            Text(nextLine).font(.caption).foregroundStyle(.secondary)
            Spacer(minLength: 0)
        }
        .padding(10)
        .frame(width: 320, alignment: .top)
        .frame(maxHeight: .infinity, alignment: .top)
        .background(Color.blue.opacity(0.08), in: RoundedRectangle(cornerRadius: 12))
        .overlay(RoundedRectangle(cornerRadius: 12).strokeBorder(Color.blue.opacity(0.35), lineWidth: 1))
    }

    private var nextLine: String {
        let after = board.cards(.upNext).first.map { " · picks up \($0.id) next" } ?? ""
        return entry.project.loaded ? "Next tick \(next)\(after)" : "No ticks while the loop is off"
    }

    private func hero(_ card: BoardCard) -> some View {
        let isLive = live?.ticket == card.id
        let recent = LogFeed.entries(log).filter { $0.kind != "idle" && $0.time != nil }.suffix(3)
        return Button { selected = selected == card.id ? nil : card.id } label: {
            VStack(alignment: .leading, spacing: 10) {
                HStack(spacing: 6) {
                    Text(card.id).font(.caption.monospaced()).foregroundStyle(.secondary)
                    Spacer()
                    let meta = [card.harness ?? "claude", live?.attempt.map { "attempt \($0)" }].compactMap { $0 }
                    chip(meta.joined(separator: " · "), .blue)
                }
                Text(card.title.isEmpty ? card.id : card.title).font(.title3.weight(.semibold))
                    .multilineTextAlignment(.leading).lineLimit(3)
                if isLive, let elapsed = NowMath.elapsed(heartbeat: live, now: now) {
                    HStack(alignment: .firstTextBaseline, spacing: 8) {
                        Text(NowMath.clock(elapsed)).font(.system(size: 30, weight: .semibold).monospacedDigit())
                        Text("elapsed · \(live?.phase ?? "")").font(.caption).foregroundStyle(.secondary)
                    }
                }
                PhaseStrip(steps: NowMath.phaseStrip(heartbeat: isLive ? live : nil))
                if !recent.isEmpty {
                    VStack(alignment: .leading, spacing: 2) {
                        ForEach(Array(recent.enumerated()), id: \.offset) { _, line in
                            Text("\(line.time ?? "") \(line.kind)  \(line.text)").lineLimit(1)
                        }
                    }
                    .font(.system(size: 11, design: .monospaced)).foregroundStyle(.secondary)
                    .padding(8).frame(maxWidth: .infinity, alignment: .leading)
                    .background(.black.opacity(0.15), in: RoundedRectangle(cornerRadius: 6))
                }
            }
            .padding(12)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(.background.opacity(0.6), in: RoundedRectangle(cornerRadius: 10))
            .overlay(RoundedRectangle(cornerRadius: 10)
                .strokeBorder(selected == card.id ? Color.accentColor : Color.blue.opacity(0.4), lineWidth: selected == card.id ? 2 : 1))
            .contentShape(RoundedRectangle(cornerRadius: 10))
        }
        .buttonStyle(.plain)
    }
}

/// What a click on a card opens: the ticket in full, its packet and Go / No when it waits on Joe,
/// Talk it through, the tracker link and its attempt history.
private struct CardDetails: View {
    let store: ProjectStore
    let entry: ProjectEntry
    let card: BoardCard
    let feed: DecisionsFeed
    let runs: [RunRecord]
    let statusCommand: Command?
    let close: () -> Void
    @State private var note = ""
    @Environment(\.openURL) private var openURL

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 12) {
                HStack(spacing: 8) {
                    Text(card.id).font(.callout.monospaced()).foregroundStyle(.secondary)
                    chip(card.column.title, columnTint(card.column))
                    if let errored = card.errored { ErroredFlag(kind: errored) }
                    Spacer()
                    Button(action: close) { Image(systemName: "xmark") }
                        .buttonStyle(.borderless).help("Close details").accessibilityLabel("Close details")
                }
                Text(card.title.isEmpty ? card.id : card.title).font(.title3.weight(.semibold))
                    .textSelection(.enabled).fixedSize(horizontal: false, vertical: true)
                if let note = card.note {
                    Text(note).foregroundStyle(.secondary).textSelection(.enabled)
                }
                if card.waiting { decision }
                actions
                history
            }
            .padding(16)
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .background(.background.opacity(0.4))
    }

    @ViewBuilder private var decision: some View {
        if let packet = card.ticket?.packet, !packet.isEmpty {
            PacketView(packet: packet)
                .padding(10)
                .background(.quaternary.opacity(0.5), in: RoundedRectangle(cornerRadius: 8))
        }
        if let answer = feed.answers[card.id] {
            Text(answer.text).foregroundStyle(.green)
        } else if let ticket = card.ticket {
            // Only these two buttons ever run `runway go|no`, and only for this ticket.
            VStack(alignment: .leading, spacing: 8) {
                TextField("Note (optional)", text: $note)
                HStack {
                    Button("Go") { send(ticket, go: true) }.keyboardShortcut(.defaultAction).disabled(!canSend)
                    Button("No") { send(ticket, go: false) }.disabled(!canSend)
                    if feed.isAnswering(card.id) { ProgressView().controlSize(.small) }
                }
            }
        }
        if let error = feed.errors[card.id] {
            Text(error).font(.caption.monospaced()).textSelection(.enabled).padding(8)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(.red.opacity(0.15), in: RoundedRectangle(cornerRadius: 6))
        }
    }

    private var actions: some View {
        HStack(spacing: 10) {
            if card.waiting || card.errored != nil || card.column == .running {
                TalkButton(store: store, project: entry.project, ticket: card.id)
            }
            if let url = card.ticket?.url.flatMap(URL.init(string:)), url.scheme?.hasPrefix("http") == true {
                Button(TicketLink.buttonTitle(tracker: entry.project.tracker)) { openURL(url) }
            }
        }
    }

    @ViewBuilder private var history: some View {
        let rows = RoundLog.history(card.id, in: runs)
        Divider()
        Text("ATTEMPTS").font(.caption2.weight(.semibold)).foregroundStyle(.secondary)
        if rows.isEmpty {
            Text("No runs logged yet.").font(.caption).foregroundStyle(.secondary)
        }
        ForEach(rows) { record in
            HStack(spacing: 6) {
                Image(systemName: icon(record.result)).foregroundStyle(color(record.result))
                Text(line(record)).font(.caption).textSelection(.enabled)
            }
        }
    }

    private func line(_ r: RunRecord) -> String {
        var parts = [r.kind == "run" ? "agent" : r.kind]
        if let attempt = r.attempt { parts.append("attempt \(attempt)") }
        if let minutes = r.minutes { parts.append("\(max(1, Int(minutes.rounded()))) min") }
        if let cost = r.costUSD, cost > 0 { parts.append(String(format: "$%.2f", cost)) }
        if r.kind == "outcome", let outcome = r.details.first(where: { $0.key == "outcome" })?.value {
            parts.append(outcome == "merged" ? "merged" : ErroredKind.words(outcome))
        }
        if let date = BoardStats.parseDate(r.at) { parts.insert(date.formatted(date: .omitted, time: .shortened), at: 0) }
        return parts.joined(separator: " · ")
    }

    private func icon(_ result: RunResult) -> String {
        switch result {
        case .pass: return "checkmark.circle.fill"
        case .fail: return "xmark.circle.fill"
        case .park: return "pause.circle.fill"
        case .unknown: return "circle"
        }
    }

    private func color(_ result: RunResult) -> Color {
        switch result {
        case .pass: return .green
        case .fail: return .red
        case .park: return .orange
        case .unknown: return .secondary
        }
    }

    private var canSend: Bool {
        entry.project.repoPath != nil && store.tools != nil && statusCommand != nil && !feed.isAnswering(card.id)
    }

    private func send(_ ticket: QueueTicket, go: Bool) {
        guard let repo = entry.project.repoPath, let tools = store.tools, let statusCommand else { return }
        let note = note
        Task {
            await feed.answer(ticket, go: go, note: note,
                              command: tools.answer(go: go, ticket: ticket.id, note: note, repo: repo),
                              status: statusCommand)
        }
    }
}

/// The log as a drawer under the board: one line when closed (the latest event), the full list when open.
private struct ActivityDrawer: View {
    let entries: [LogEntry]
    let repo: String?
    @Binding var open: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack(spacing: 10) {
                Button { withAnimation(.easeInOut(duration: 0.15)) { open.toggle() } } label: {
                    HStack(spacing: 10) {
                        Image(systemName: open ? "chevron.down" : "chevron.up").font(.caption)
                        Text("Activity").font(.callout.weight(.semibold))
                        if !open, let last = entries.last(where: { $0.kind != "idle" }) {
                            Text("\(last.time ?? "") \(last.kind)  \(last.text)")
                                .font(.system(size: 11, design: .monospaced)).foregroundStyle(.secondary).lineLimit(1)
                        }
                        Spacer()
                    }
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                if let repo {
                    Button {
                        NSWorkspace.shared.activateFileViewerSelecting(
                            [URL(fileURLWithPath: repo).appendingPathComponent("_pm/runway.log")])
                    } label: { Label("Show log", systemImage: "doc.text.magnifyingglass") }
                    .buttonStyle(.borderless).font(.caption).foregroundStyle(.secondary)
                }
            }
            .padding(.horizontal, 16).frame(height: 34)
            if open {
                LogList(entries: entries)
                    .frame(height: 220)
                    .padding(.horizontal, 16).padding(.bottom, 12)
            }
        }
    }
}

/// A project in error: its detail in full, the last log lines and Talk it through.
private struct ErrorBanner: View {
    let store: ProjectStore
    let entry: ProjectEntry
    let lines: [String]

    var body: some View {
        let tail = lines.filter { !$0.trimmingCharacters(in: .whitespaces).isEmpty }.suffix(6)
        VStack(alignment: .leading, spacing: 8) {
            Label(entry.status.detail, systemImage: "exclamationmark.triangle.fill")
                .font(.headline).foregroundStyle(.red).textSelection(.enabled)
            if tail.isEmpty {
                Text("No log lines yet.").font(.caption).foregroundStyle(.secondary)
            } else {
                Text(tail.joined(separator: "\n")).font(.system(size: 11, design: .monospaced))
                    .textSelection(.enabled).lineLimit(8)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
            TalkButton(store: store, project: entry.project)
        }
        .padding(12).frame(maxWidth: .infinity, alignment: .leading)
        .background(.red.opacity(0.12), in: RoundedRectangle(cornerRadius: 10))
        .overlay(RoundedRectangle(cornerRadius: 10).strokeBorder(Color.red.opacity(0.5), lineWidth: 1))
    }
}

/// A packet drawn from `PacketMarkdown` blocks; inline bold, code and links come from `AttributedString`.
struct PacketView: View {
    let packet: String

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            ForEach(Array(PacketMarkdown.blocks(packet).enumerated()), id: \.offset) { _, block in
                switch block {
                case .heading(let level, let text):
                    inline(text).font(level <= 2 ? .title3.bold() : .headline).padding(.top, 4)
                case .paragraph(let text):
                    inline(text)
                case .bullet(let text):
                    item("•", text)
                case .numbered(let number, let text):
                    item("\(number).", text)
                case .code(let text):
                    Text(text).font(.system(size: 11, design: .monospaced)).textSelection(.enabled)
                        .frame(maxWidth: .infinity, alignment: .leading).padding(8)
                        .background(.black.opacity(0.06), in: RoundedRectangle(cornerRadius: 6))
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private func item(_ marker: String, _ text: String) -> some View {
        let recommended = PacketMarkdown.isRecommended(text)
        return HStack(alignment: .firstTextBaseline, spacing: 6) {
            Text(marker).foregroundStyle(.secondary)
            inline(text)
            if recommended {
                Text("recommended").font(.caption2.bold()).padding(.horizontal, 6).padding(.vertical, 1)
                    .background(.green.opacity(0.25), in: Capsule())
            }
        }
    }

    private func inline(_ text: String) -> Text {
        let options = AttributedString.MarkdownParsingOptions(interpretedSyntax: .inlineOnlyPreservingWhitespace)
        return Text((try? AttributedString(markdown: text, options: options)) ?? AttributedString(text))
    }
}
