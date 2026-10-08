import SwiftUI
import AppKit
import RunwayCore

struct RunsTab: View {
    let store: ProjectStore
    let entry: ProjectEntry
    @State private var snapshot: RunsSnapshot?
    @State private var message: String?
    @State private var selected: RunRecord.ID?

    private var repo: String? { entry.project.repoPath }

    var body: some View {
        VStack(spacing: 0) {
            header
            Divider()
            if let snapshot {
                if snapshot.records.isEmpty {
                    Text("No runs logged yet.").foregroundStyle(.secondary).frame(maxWidth: .infinity, maxHeight: .infinity)
                } else {
                    table(snapshot.records)
                    Divider()
                    footer(snapshot.totals)
                }
                if let id = selected, let record = snapshot.records.first(where: { $0.id == id }) {
                    Divider()
                    details(record)
                } else if let body = snapshot.prBody {
                    Divider()
                    finish(body)
                }
            } else {
                Text("Loading…").foregroundStyle(.secondary).frame(maxWidth: .infinity, maxHeight: .infinity)
            }
        }
        .task(id: entry.project.label) {
            while !Task.isCancelled {
                await reload()
                try? await Task.sleep(nanoseconds: 10 * 1_000_000_000)
            }
        }
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Spacer()
                Button("Write retro prompt") { Task { await writeRetro() } }
                    .disabled(repo == nil || store.tools == nil)
            }
            if let message {
                Text(message).font(.caption).textSelection(.enabled).padding(8).frame(maxWidth: .infinity, alignment: .leading)
                    .background(.red.opacity(0.15), in: RoundedRectangle(cornerRadius: 6))
            }
        }
        .padding(10)
    }

    // A Table over 10k rows is lazy; the parse happens off the main actor in `reload`.
    private func table(_ records: [RunRecord]) -> some View {
        Table(records, selection: $selected) {
            TableColumn("When") { Text($0.at).monospacedDigit() }.width(min: 120, ideal: 150)
            TableColumn("Ticket") { record in
                if let url = linearURL(record.ticket) {
                    Link(record.ticket, destination: url).font(.body.monospaced()).help("Open \(record.ticket) in Linear")
                } else {
                    Text(record.ticket).font(.body.monospaced())
                }
            }.width(min: 60, ideal: 80)
            TableColumn("Kind") { Text($0.kind) }.width(min: 50, ideal: 70)
            TableColumn("Harness") { Text($0.harness ?? "—") }.width(min: 50, ideal: 70)
            TableColumn("Attempt") { Text($0.attempt.map(String.init) ?? "—") }.width(min: 40, ideal: 55)
            TableColumn("Result") { record in
                Text(record.result.rawValue).foregroundStyle(resultColor(record.result))
            }.width(min: 50, ideal: 60)
            TableColumn("Min") { Text($0.minutes.map { String(format: "%.1f", $0) } ?? "—").monospacedDigit() }
                .width(min: 40, ideal: 50)
            TableColumn("Tokens") { Text($0.tokens.map(String.init) ?? "—").monospacedDigit() }.width(min: 60, ideal: 80)
            TableColumn("Cost") { Text($0.costUSD.map { String(format: "$%.2f", $0) } ?? "—").monospacedDigit() }
                .width(min: 50, ideal: 60)
            TableColumn("") { record in
                if let id = record.sessionID, !id.isEmpty {
                    Button("Session") { openSession(id) }.buttonStyle(.link)
                }
            }.width(min: 60, ideal: 70)
        }
    }

    private func footer(_ totals: RunTotals) -> some View {
        HStack(spacing: 16) {
            Text("\(totals.rows) rows")
            Spacer()
            Text(String(format: "%.1f min", totals.minutes))
            Text("\(totals.tokens) tokens")
            Text(String(format: "$%.2f", totals.costUSD))
        }
        .font(.callout.monospacedDigit().bold()).padding(10)
    }

    private func linearURL(_ ticket: String) -> URL? {
        store.snapshot(for: entry.project.label)?.urls[ticket]
    }

    /// The selected row: what it was, links out, and every field the table leaves out.
    private func details(_ record: RunRecord) -> some View {
        let title = store.snapshot(for: entry.project.label)?.titles[record.ticket] ?? ""
        return VStack(alignment: .leading, spacing: 8) {
            HStack(alignment: .firstTextBaseline, spacing: 8) {
                Text(record.ticket).font(.headline.monospaced())
                if !title.isEmpty { Text(title).font(.headline).lineLimit(1) }
                Spacer()
                if let url = linearURL(record.ticket) {
                    Link(destination: url) { Label("Open in Linear", systemImage: "arrow.up.right.square") }
                }
                if let id = record.sessionID, !id.isEmpty {
                    Button { openSession(id) } label: { Label("Show session", systemImage: "doc.text.magnifyingglass") }
                        .buttonStyle(.link)
                }
                Button { selected = nil } label: { Image(systemName: "xmark.circle.fill") }
                    .buttonStyle(.borderless).foregroundStyle(.secondary).help("Close details")
            }
            Text([record.at, record.kind, record.attempt.map { "attempt \($0)" }, record.result.rawValue,
                  record.minutes.map { String(format: "%.1f min", $0) }, record.costUSD.map { String(format: "$%.2f", $0) }]
                .compactMap { $0 }.joined(separator: "  ·  "))
                .font(.callout).foregroundStyle(.secondary)
            ScrollView {
                Grid(alignment: .leading, horizontalSpacing: 16, verticalSpacing: 4) {
                    ForEach(record.details, id: \.self) { item in
                        GridRow {
                            Text(item.key).foregroundStyle(.secondary)
                            Text(item.value).textSelection(.enabled).lineLimit(3)
                        }
                    }
                }
                .font(.system(size: 11, design: .monospaced))
                .frame(maxWidth: .infinity, alignment: .leading)
            }
            .frame(maxHeight: 160)
        }
        .padding(12)
    }

    private func finish(_ body: String) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text("Finish").font(.headline)
            ScrollView {
                Text(body).font(.system(size: 11, design: .monospaced)).textSelection(.enabled)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
            .frame(maxHeight: 160)
        }
        .padding(10)
    }

    private func resultColor(_ result: RunResult) -> Color {
        switch result {
        case .pass: return .green
        case .fail: return .red
        case .park: return .orange
        case .unknown: return .secondary
        }
    }

    private func reload() async {
        guard let repo else { snapshot = .empty; return }
        let url = URL(fileURLWithPath: repo)
        snapshot = await Task.detached { RunsSnapshot.load(repo: url) }.value
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

    private func writeRetro() async {
        guard let repo, let tools = store.tools else { return }
        let result = await CommandRunner.run(tools.retro(repo: repo))
        guard result.succeeded else { message = "retro failed: \(result.failureMessage)"; return }
        message = nil
        NSWorkspace.shared.open(URL(fileURLWithPath: repo).appendingPathComponent("_pm/runway-retro-prompt.md"))
    }
}
