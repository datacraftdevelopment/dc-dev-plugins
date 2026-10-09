import SwiftUI
import RunwayCore

struct DecisionsTab: View {
    let store: ProjectStore
    let entry: ProjectEntry
    @State private var feed = DecisionsFeed()
    @Environment(\.openURL) private var openURL

    var body: some View {
        VStack(spacing: 0) {
            header
            Divider()
            let cards = feed.cards
            if cards.isEmpty {
                Text(feed.queue == nil ? (feed.isRefreshing ? "Loading decisions…" : "No status yet.") : "Nothing waiting on you.")
                    .foregroundStyle(.secondary).frame(maxWidth: .infinity, maxHeight: .infinity)
            } else {
                ScrollView {
                    VStack(spacing: 12) {
                        ForEach(cards) { card in
                            DecisionCardView(card: card, feed: feed, store: store, project: entry.project, repo: entry.project.repoPath, tracker: entry.project.tracker, tools: store.tools,
                                             statusCommand: statusCommand, open: open)
                        }
                    }
                    .padding(12)
                }
            }
        }
        // Fetches on open and every minute; it calls the tracker, so no faster.
        .task(id: entry.project.label) {
            while !Task.isCancelled {
                await reload()
                try? await Task.sleep(nanoseconds: 60 * 1_000_000_000)
            }
        }
    }

    private var statusCommand: Command? {
        guard let repo = entry.project.repoPath, let tools = store.tools else { return nil }
        return tools.status(repo: repo)
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                TimelineView(.periodic(from: .now, by: 15)) { context in
                    Text(feed.fetchedAt.map { "Updated \(QueueFeed.ageText(from: $0, now: context.date))" } ?? "Not fetched yet")
                        .font(.caption).foregroundStyle(.secondary)
                }
                if feed.isRefreshing { ProgressView().controlSize(.small) }
                Spacer()
                Button("Refresh") { Task { await reload() } }.disabled(feed.isRefreshing)
            }
            if let error = feed.error {
                Text(feed.queue == nil ? error : "\(error) Showing the last good result.")
                    .font(.caption).textSelection(.enabled).padding(8).frame(maxWidth: .infinity, alignment: .leading)
                    .background(.red.opacity(0.15), in: RoundedRectangle(cornerRadius: 6))
            }
        }
        .padding(10)
    }

    private func reload() async {
        guard let command = statusCommand else { return }
        await feed.refresh(command)
    }

    private func open(_ url: String?) {
        if let url = url.flatMap(URL.init(string:)), url.scheme?.hasPrefix("http") == true { openURL(url) }
    }
}

private struct DecisionCardView: View {
    let card: DecisionCard
    let feed: DecisionsFeed
    let store: ProjectStore
    let project: Project
    let repo: String?
    let tracker: String?
    let tools: RunwayTools?
    let statusCommand: Command?
    let open: (String?) -> Void
    @State private var note = ""

    var body: some View {
        let ticket = card.ticket
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Text(ticket.id).font(.headline.monospaced())
                Text(ticket.title).font(.headline).lineLimit(2)
                Spacer()
                if let errored = ticket.errored { ErroredFlag(kind: errored) }
                if ticket.url != nil { Button(TicketLink.buttonTitle(tracker: tracker)) { open(ticket.url) } }
            }
            if let packet = ticket.packet, !packet.isEmpty {
                PacketView(packet: packet)
            } else {
                Text("No decision packet yet.").foregroundStyle(.secondary)
            }
            Divider()
            if let answer = card.answer {
                Text(answer.text).foregroundStyle(.green)
            } else {
                // Only these two buttons ever run `runway go|no`, and only for this ticket.
                TextField("Note (optional)", text: $note)
                HStack {
                    Button("Go") { send(go: true) }.keyboardShortcut(.defaultAction).disabled(!canSend)
                    Button("No") { send(go: false) }.disabled(!canSend)
                    if feed.isAnswering(ticket.id) { ProgressView().controlSize(.small) }
                    TalkButton(store: store, project: project, ticket: ticket.id)
                }
            }
            if let error = feed.errors[ticket.id] {
                Text(error).font(.caption.monospaced()).textSelection(.enabled).padding(8)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(.red.opacity(0.15), in: RoundedRectangle(cornerRadius: 6))
            }
        }
        .padding(12)
        .background(.quaternary, in: RoundedRectangle(cornerRadius: 10))
    }

    private var canSend: Bool {
        repo != nil && tools != nil && statusCommand != nil && !feed.isAnswering(card.ticket.id)
    }

    private func send(go: Bool) {
        guard let repo, let tools, let statusCommand else { return }
        let ticket = card.ticket, note = note
        Task {
            await feed.answer(ticket, go: go, note: note,
                              command: tools.answer(go: go, ticket: ticket.id, note: note, repo: repo),
                              status: statusCommand)
        }
    }
}

/// A packet drawn from `PacketMarkdown` blocks; inline bold, code and links come from `AttributedString`.
private struct PacketView: View {
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
