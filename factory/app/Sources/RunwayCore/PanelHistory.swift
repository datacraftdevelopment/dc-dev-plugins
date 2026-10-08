import Foundation

/// One ticket the loop finished with: its outcome line plus every agent call for it since its previous outcome.
public struct FinishedTicket: Equatable, Sendable, Identifiable {
    /// The outcome's line number in `runway-runs.jsonl`, so rows stay stable as the file grows.
    public let id: Int
    public let ticket: String
    /// `done`, `needs-human` or `stopped`.
    public let result: String
    public let attempts: Int
    public let detail: String
    public let finishedAt: Date?
    /// run, fix, review and pr calls, oldest first.
    public let steps: [RunRecord]

    public var agentSecs: Double { steps.reduce(0) { $0 + ($1.secs ?? 0) } }
    public var costUSD: Double { steps.reduce(0) { $0 + ($1.costUSD ?? 0) } }
    public var tokens: Int { steps.reduce(0) { $0 + ($1.tokens ?? 0) } }
    public var turns: Int { steps.reduce(0) { $0 + (Int($1.details.first { $0.key == "num_turns" }?.value ?? "") ?? 0) } }

    /// Start of the first call (its line is written when it ends) to the outcome; never less than the agent time.
    /// The log keeps minutes only, so this can be up to a minute out.
    public var wallSecs: Double? {
        guard let end = finishedAt, let first = steps.first, let firstEnd = PanelHistory.date(first.at) else {
            return steps.isEmpty ? nil : agentSecs
        }
        return max(end.timeIntervalSince(firstEnd.addingTimeInterval(-(first.secs ?? 0))), agentSecs)
    }

    /// Marked done, but no call did any work: every one used no tokens. The engine before DAT-40 did this when
    /// the agent failed to start.
    public var noWork: Bool { result == "done" && !steps.isEmpty && tokens == 0 }
}

/// The integration branch's finish step: check, review, fix pass and the PR draft.
public struct FinishRecord: Equatable, Sendable, Identifiable {
    public let id: Int
    public let finishedAt: Date?
    public let checkPassed: Bool?
    public let findings: Bool?
    public let fix: String
    public let pr: String
    public let steps: [RunRecord]

    public var costUSD: Double { steps.reduce(0) { $0 + ($1.costUSD ?? 0) } }
}

/// A row of the panel's Finished list. Neighbouring no-work tickets fold into one row so they can't pass for real work.
public enum FinishedRow: Equatable, Sendable, Identifiable {
    case ticket(FinishedTicket)
    case noWork([FinishedTicket])
    case finish(FinishRecord)

    public var id: String {
        switch self {
        case .ticket(let t): return "t\(t.id)"
        case .noWork(let group): return "n\(group.first?.id ?? 0)"
        case .finish(let f): return "f\(f.id)"
        }
    }

    public var finishedAt: Date? {
        switch self {
        case .ticket(let t): return t.finishedAt
        case .noWork(let group): return group.first?.finishedAt
        case .finish(let f): return f.finishedAt
        }
    }
}

/// The Finished rows of one calendar day, newest first. `Row` is a `FinishedRow`, or one tagged with its project.
public struct FinishedDay<Row>: Identifiable {
    public var id: String { label }
    public let label: String
    public let rows: [Row]
}

extension FinishedDay: Equatable where Row: Equatable {}
extension FinishedDay: Sendable where Row: Sendable {}

public enum PanelHistory {
    /// Finished rows from `runway-runs.jsonl`, newest first, at most `limit` of them.
    public static func rows(_ data: Data, limit: Int = 60) -> [FinishedRow] {
        var pending: [String: [RunRecord]] = [:]
        var out: [FinishedRow] = []
        for (record, raw) in zip(RunsLog.parse(data).reversed(), rawLines(data)) {
            switch record.kind {
            case "outcome":
                out.append(.ticket(FinishedTicket(
                    id: record.id, ticket: record.ticket, result: raw["result"] as? String ?? "",
                    attempts: record.attempt ?? 0, detail: raw["detail"] as? String ?? "", finishedAt: date(record.at),
                    steps: pending.removeValue(forKey: record.ticket) ?? [])))
            case "finish":
                let check = raw["check_exit"] as? NSNumber
                out.append(.finish(FinishRecord(
                    id: record.id, finishedAt: date(record.at), checkPassed: check.map { $0.intValue == 0 },
                    findings: raw["findings"] as? Bool, fix: raw["fix"] as? String ?? "", pr: raw["pr"] as? String ?? "",
                    steps: pending.removeValue(forKey: record.ticket) ?? [])))
            case "":
                continue
            default:
                pending[record.ticket, default: []].append(record)
            }
        }
        return fold(Array(out.reversed().prefix(limit)))
    }

    /// Splits rows (newest first) into days: Today, Yesterday, then `Mon 6 Oct`. Rows with no date go under Earlier.
    public static func days<Row>(_ rows: [Row], date: (Row) -> Date?, now: Date = Date(),
                                 calendar: Calendar = .current) -> [FinishedDay<Row>] {
        var days: [FinishedDay<Row>] = []
        for row in rows {
            let label = date(row).map { dayLabel($0, now: now, calendar: calendar) } ?? "Earlier"
            if let last = days.last, last.label == label {
                days[days.count - 1] = FinishedDay(label: label, rows: last.rows + [row])
            } else {
                days.append(FinishedDay(label: label, rows: [row]))
            }
        }
        return days
    }

    public static func days(_ rows: [FinishedRow], now: Date = Date(),
                            calendar: Calendar = .current) -> [FinishedDay<FinishedRow>] {
        days(rows, date: \.finishedAt, now: now, calendar: calendar)
    }

    public static func dayLabel(_ date: Date, now: Date, calendar: Calendar = .current) -> String {
        if calendar.isDate(date, inSameDayAs: now) { return "Today" }
        if let yesterday = calendar.date(byAdding: .day, value: -1, to: now), calendar.isDate(date, inSameDayAs: yesterday) {
            return "Yesterday"
        }
        let formatter = DateFormatter()
        formatter.calendar = calendar
        formatter.timeZone = calendar.timeZone
        formatter.dateFormat = "EEE d MMM"
        return formatter.string(from: date)
    }

    /// Tickets that really finished done; no-work rows and finish steps don't count.
    public static func doneCount(_ rows: [FinishedRow]) -> Int {
        rows.reduce(0) { count, row in
            if case .ticket(let t) = row, t.result == "done" { return count + 1 }
            return count
        }
    }

    public static func cost(of rows: [FinishedRow]) -> Double {
        rows.reduce(0) { total, row in
            switch row {
            case .ticket(let t): return total + t.costUSD
            case .noWork(let group): return total + group.reduce(0) { $0 + $1.costUSD }
            case .finish(let f): return total + f.costUSD
            }
        }
    }

    /// `45s`, `7m`, `1h 12m`.
    public static func duration(_ seconds: Double) -> String {
        let s = max(0, Int(seconds.rounded()))
        if s < 60 { return "\(s)s" }
        if s < 3600 { return "\(s / 60)m" }
        return "\(s / 3600)h \(s % 3600 / 60)m"
    }

    /// `$1.51`, `$0`.
    public static func cost(_ usd: Double) -> String { usd < 0.005 ? "$0" : String(format: "$%.2f", usd) }

    /// `850`, `29.5k`, `1.2M`.
    public static func tokens(_ count: Int) -> String {
        if count < 1000 { return "\(count)" }
        if count < 1_000_000 { return String(format: "%.1fk", Double(count) / 1000) }
        return String(format: "%.1fM", Double(count) / 1_000_000)
    }

    /// `2026-10-08 16:56 EDT` as the engine writes it. A zone the formatter can't read falls back to local time.
    public static func date(_ text: String) -> Date? {
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.dateFormat = "yyyy-MM-dd HH:mm zzz"
        if let date = formatter.date(from: text) { return date }
        formatter.dateFormat = "yyyy-MM-dd HH:mm"
        formatter.timeZone = .current
        return formatter.date(from: String(text.prefix(16)))
    }

    // MARK: private

    /// Neighbouring no-work tickets become one `.noWork` row; a lone one too, so it is never shown as done.
    private static func fold(_ rows: [FinishedRow]) -> [FinishedRow] {
        var out: [FinishedRow] = []
        for row in rows {
            guard case .ticket(let t) = row, t.noWork else { out.append(row); continue }
            if case .noWork(let group) = out.last {
                out[out.count - 1] = .noWork(group + [t])
            } else {
                out.append(.noWork([t]))
            }
        }
        return out
    }

    /// The JSON objects in file order, aligned with `RunsLog.parse` (which skips the same lines).
    private static func rawLines(_ data: Data) -> [[String: Any]] {
        data.split(separator: UInt8(ascii: "\n"), omittingEmptySubsequences: true).compactMap {
            (try? JSONSerialization.jsonObject(with: $0)) as? [String: Any]
        }
    }
}
