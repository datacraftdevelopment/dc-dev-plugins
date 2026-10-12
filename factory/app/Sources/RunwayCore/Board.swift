import Foundation

/// The window's board columns, left to right: what's stuck, what waits on Joe, the queue, the ticket in flight,
/// and what this round already merged.
public enum BoardColumn: String, CaseIterable, Equatable, Sendable, Identifiable {
    case blocked, needsYou, upNext, running, done
    public var id: String { rawValue }

    public var title: String {
        switch self {
        case .blocked: return "Blocked"
        case .needsYou: return "Needs you"
        case .upNext: return "Up next"
        case .running: return "Running"
        case .done: return "Done this round"
        }
    }

    public var hint: String {
        switch self {
        case .blocked: return "Waiting on other tickets"
        case .needsYou: return "Answer here or talk it through"
        case .upNext: return "In the order the tick takes them"
        case .running: return ""
        case .done: return "Merged into the integration branch"
        }
    }
}

/// One ticket on the board. Every field but the id may be empty: a done ticket can come only from the runs log.
public struct BoardCard: Equatable, Sendable, Identifiable {
    public let id: String
    public let title: String
    public let column: BoardColumn
    /// The one line under the title: why it waits, what blocks it, how long it took.
    public let note: String?
    /// The ticket as status gave it; nil for a done card status no longer lists.
    public let ticket: QueueTicket?
    /// Kind of the latest attempt that didn't merge.
    public let errored: String?
    /// True for a ticket waiting on a go or no (not one in Needs you only because it errored).
    public let waiting: Bool
    /// Up next: a prep pass runs before the build.
    public let needsPrep: Bool
    public let harness: String?
}

/// Status's groups plus the runs log, laid out as columns. Pure, so the rules are tested here and the view only draws.
public struct Board: Equatable, Sendable {
    public let columns: [BoardColumn: [BoardCard]]

    public func cards(_ column: BoardColumn) -> [BoardCard] { columns[column] ?? [] }

    public func card(_ id: String?) -> BoardCard? {
        guard let id else { return nil }
        return BoardColumn.allCases.lazy.compactMap { column in self.cards(column).first { $0.id == id } }.first
    }

    /// Each ticket lands in one column:
    /// - running: status's `running` group, plus the heartbeat's live ticket wherever status still has it;
    /// - needs you: the `waiting` group, then errored tickets that aren't running or done;
    /// - up next: `ready_auto` then `ready_prep`, in queue order;
    /// - blocked: the `blocked` group;
    /// - done: tickets this round merged (`RoundLog.merged`), newest first.
    public static func build(queue: QueueStatus?, liveTicket: String? = nil, runs: [RunRecord] = []) -> Board {
        let tickets = queue?.tickets ?? []
        let byID = Dictionary(tickets.map { ($0.id, $0) }, uniquingKeysWith: { first, _ in first })
        var placed = Set<String>()
        var columns: [BoardColumn: [BoardCard]] = [:]

        func add(_ column: BoardColumn, _ card: BoardCard) {
            guard !placed.contains(card.id) else { return }
            placed.insert(card.id)
            columns[column, default: []].append(card)
        }
        func card(_ t: QueueTicket, _ column: BoardColumn, note: String?, waiting: Bool = false, prep: Bool = false) -> BoardCard {
            BoardCard(id: t.id, title: t.title, column: column, note: note, ticket: t, errored: t.errored,
                      waiting: waiting, needsPrep: prep, harness: t.harness)
        }
        func group(_ key: String) -> [QueueTicket] { (queue?.group(key) ?? []).compactMap { byID[$0] } }

        var running = group("running")
        if let live = liveTicket, !running.contains(where: { $0.id == live }), let t = byID[live] { running.insert(t, at: 0) }
        for t in running { add(.running, card(t, .running, note: nil)) }

        for t in group("waiting") {
            add(.needsYou, card(t, .needsYou, note: t.reason ?? t.waitingOn, waiting: true))
        }
        let done = Set(queue?.group("done") ?? [])
        for t in tickets where t.errored != nil && !done.contains(t.id) {
            add(.needsYou, card(t, .needsYou, note: t.errored.map(ErroredKind.words)))
        }

        let auto = group("ready_auto"), prep = group("ready_prep")
        for (index, t) in auto.enumerated() {
            add(.upNext, card(t, .upNext, note: index == 0 ? "Next in line" : nil))
        }
        for t in prep {
            add(.upNext, card(t, .upNext, note: auto.isEmpty && t.id == prep.first?.id ? "Next in line, after a prep pass" : "A prep pass runs first", prep: true))
        }

        for t in group("blocked") {
            add(.blocked, card(t, .blocked, note: t.blockedBy.isEmpty ? nil : "Waits on " + t.blockedBy.joined(separator: ", ")))
        }

        for merged in RoundLog.merged(runs) {
            let t = byID[merged.ticket]
            add(.done, BoardCard(id: merged.ticket, title: t?.title ?? "", column: .done, note: merged.note,
                                 ticket: t, errored: nil, waiting: false, needsPrep: false, harness: t?.harness))
        }
        return Board(columns: columns)
    }
}

/// One ticket the current round merged, with what it took.
public struct MergedTicket: Equatable, Sendable {
    public let ticket: String
    public let secs: Double
    public let costUSD: Double

    /// "14 min · $1.10"; the parts that are zero are left out.
    public var note: String? {
        var parts: [String] = []
        if secs > 0 { parts.append("\(max(1, Int((secs / 60).rounded()))) min") }
        if costUSD > 0 { parts.append(String(format: "$%.2f", costUSD)) }
        return parts.isEmpty ? nil : parts.joined(separator: " · ")
    }
}

/// The runs log read as rounds: a round ends at a `finish` row.
public enum RoundLog {
    /// Records since the last `finish`, newest first (the order `RunsLog.parse` gives).
    public static func currentRound(_ records: [RunRecord]) -> ArraySlice<RunRecord> {
        let end = records.firstIndex { $0.kind == "finish" } ?? records.endIndex
        return records[..<end]
    }

    /// Tickets with a `done` outcome this round, newest first, each with the time and cost of its agent calls this round.
    public static func merged(_ records: [RunRecord]) -> [MergedTicket] {
        let round = currentRound(records)
        var seen = Set<String>()
        var out: [MergedTicket] = []
        for record in round where record.kind == "outcome" && record.result == .pass && !seen.contains(record.ticket) {
            seen.insert(record.ticket)
            let calls = round.filter { $0.ticket == record.ticket && ($0.kind == "run" || $0.kind == "prep") }
            out.append(MergedTicket(ticket: record.ticket, secs: calls.reduce(0) { $0 + ($1.secs ?? 0) },
                                    costUSD: calls.reduce(0) { $0 + ($1.costUSD ?? 0) }))
        }
        return out
    }

    /// One ticket's prep, agent, check and outcome rows, oldest first, at most `limit` (the latest ones).
    public static func history(_ ticket: String, in records: [RunRecord], limit: Int = 12) -> [RunRecord] {
        let rows = records.filter { $0.ticket == ticket && ["prep", "run", "check", "outcome"].contains($0.kind) }
        return Array(rows.prefix(limit).reversed())
    }
}

/// The strip of numbers above the board.
public struct BoardStats: Equatable, Sendable {
    public let mergedThisRound: Int
    public let spendToday: Double
    public let tokensToday: Int
    public let needsYou: Int

    /// "Today" is the local calendar day of `now`; a record's `at` is ISO-8601.
    public static func make(board: Board, runs: [RunRecord], now: Date, calendar: Calendar = .current) -> BoardStats {
        let today = runs.filter { record in
            parseDate(record.at).map { calendar.isDate($0, inSameDayAs: now) } ?? false
        }
        return BoardStats(mergedThisRound: board.cards(.done).count,
                          spendToday: today.reduce(0) { $0 + ($1.costUSD ?? 0) },
                          tokensToday: today.reduce(0) { $0 + ($1.tokens ?? 0) },
                          needsYou: board.cards(.needsYou).count)
    }

    /// "1.9M", "820k", "512".
    public static func tokens(_ n: Int) -> String {
        if n >= 1_000_000 { return String(format: "%.1fM", Double(n) / 1_000_000) }
        if n >= 1_000 { return "\(n / 1_000)k" }
        return "\(n)"
    }

    /// A runs-log `at` (ISO-8601, with or without fractional seconds) as a date.
    public static func parseDate(_ text: String) -> Date? {
        let plain = ISO8601DateFormatter()
        if let date = plain.date(from: text) { return date }
        let fractional = ISO8601DateFormatter()
        fractional.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return fractional.date(from: text)
    }
}
