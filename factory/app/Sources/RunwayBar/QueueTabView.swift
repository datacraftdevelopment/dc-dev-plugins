import SwiftUI
import RunwayCore

struct QueueTab: View {
    let store: ProjectStore
    let entry: ProjectEntry
    @State private var feed = QueueFeed()
    @Environment(\.openURL) private var openURL

    var body: some View {
        VStack(spacing: 0) {
            header
            Divider()
            if let queue = feed.queue {
                let sections = queue.sections
                List {
                    section("Runs next", sections.runsNext, numbered: true)
                    section("Waiting on you", sections.waiting)
                    section("Blocked", sections.blocked)
                    section("Done", sections.done)
                }
            } else {
                Text(feed.isRefreshing ? "Loading the queue…" : "No queue yet.")
                    .foregroundStyle(.secondary).frame(maxWidth: .infinity, maxHeight: .infinity)
            }
        }
        // Fetches on open and every minute; it calls Linear, so no faster. The fetch itself runs off the main actor.
        .task(id: entry.project.label) {
            while !Task.isCancelled {
                await reload()
                try? await Task.sleep(nanoseconds: 60 * 1_000_000_000)
            }
        }
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
        guard let repo = entry.project.repoPath, let tools = store.tools else { return }
        await feed.refresh(tools.status(repo: repo))
    }

    @ViewBuilder private func section(_ title: String, _ tickets: [QueueTicket], numbered: Bool = false) -> some View {
        Section("\(title) (\(tickets.count))") {
            if tickets.isEmpty {
                Text("Nothing").foregroundStyle(.secondary)
            }
            ForEach(Array(tickets.enumerated()), id: \.element.id) { index, ticket in
                row(ticket, number: numbered ? index + 1 : nil)
            }
        }
    }

    private func row(_ ticket: QueueTicket, number: Int?) -> some View {
        Button {
            if let url = ticket.url.flatMap(URL.init(string:)), url.scheme?.hasPrefix("http") == true { openURL(url) }
        } label: {
            HStack(spacing: 8) {
                if let number { Text("\(number).").monospacedDigit().foregroundStyle(.secondary) }
                Text(ticket.id).font(.body.monospaced())
                Text(ticket.title).lineLimit(1)
                Spacer()
                if !ticket.blockedBy.isEmpty {
                    Text("blocked by \(ticket.blockedBy.joined(separator: ", "))").font(.caption).foregroundStyle(.secondary)
                }
                chip(ticket.gate, .gray)
                if let harness = ticket.harness { chip(harness, .blue) }
            }
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
    }

    private func chip(_ text: String, _ color: Color) -> some View {
        Text(text).font(.caption2.bold()).padding(.horizontal, 6).padding(.vertical, 1)
            .background(color.opacity(0.2), in: Capsule())
    }
}
