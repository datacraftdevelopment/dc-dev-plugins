import Foundation

public enum RunResult: String, Equatable, Sendable {
    case pass, fail, park, unknown
}

/// One line of `_pm/runway-runs.jsonl`. Every field but `kind` may be missing.
public struct RunRecord: Equatable, Sendable, Identifiable {
    public let id: Int  // line number in the file, so rows stay distinct and stable
    public let at: String
    public let kind: String
    public let ticket: String
    public let harness: String?
    public let attempt: Int?
    public let result: RunResult
    public let secs: Double?
    public let tokens: Int?
    public let costUSD: Double?
    public let sessionID: String?
    /// Every other top-level value in the line, for the details pane: (key, value) in a stable order.
    public var details: [RunDetail] = []

    public var minutes: Double? { secs.map { $0 / 60 } }
}

public struct RunDetail: Equatable, Sendable, Hashable {
    public let key: String
    public let value: String
}

public struct RunTotals: Equatable, Sendable {
    public var rows = 0
    public var secs = 0.0
    public var tokens = 0
    public var costUSD = 0.0

    public var minutes: Double { secs / 60 }
}

public enum RunsLog {
    /// Newest first. Blank lines, bad JSON and lines that aren't objects are skipped; the log is append-only,
    /// so file order is time order.
    public static func parse(_ data: Data) -> [RunRecord] {
        var records: [RunRecord] = []
        var lineNumber = 0
        for line in data.split(separator: UInt8(ascii: "\n"), omittingEmptySubsequences: true) {
            lineNumber += 1
            guard let object = (try? JSONSerialization.jsonObject(with: line)) as? [String: Any] else { continue }
            records.append(record(object, id: lineNumber))
        }
        return records.reversed()
    }

    public static func totals(_ records: [RunRecord]) -> RunTotals {
        var totals = RunTotals()
        for record in records {
            totals.rows += 1
            totals.secs += record.secs ?? 0
            totals.tokens += record.tokens ?? 0
            totals.costUSD += record.costUSD ?? 0
        }
        return totals
    }

    static func record(_ raw: [String: Any], id: Int) -> RunRecord {
        let kind = raw["kind"] as? String ?? ""
        let usage = raw["usage"] as? [String: Any]
        let tokens = usage.map { (int($0["input_tokens"]) ?? 0) + (int($0["output_tokens"]) ?? 0) }
        return RunRecord(id: id, at: raw["at"] as? String ?? "", kind: kind, ticket: raw["ticket"] as? String ?? "",
                         harness: raw["harness"] as? String, attempt: int(raw["attempt"] ?? raw["attempts"]),
                         result: result(kind: kind, raw: raw), secs: double(raw["secs"]), tokens: tokens,
                         costUSD: double(raw["cost_usd"]), sessionID: raw["session_id"] as? String,
                         details: details(raw))
    }

    /// Keys the table already shows, left out of the details pane.
    static let shownKeys: Set<String> = ["at", "kind", "ticket", "harness", "attempt", "attempts", "secs", "cost_usd",
                                         "session_id", "usage"]

    /// Scalar fields not in the table, plus the token breakdown from `usage`; empty strings are skipped.
    static func details(_ raw: [String: Any]) -> [RunDetail] {
        var out: [RunDetail] = []
        for key in raw.keys.sorted() where !shownKeys.contains(key) {
            guard let text = scalar(raw[key]), !text.isEmpty else { continue }
            out.append(RunDetail(key: key, value: text))
        }
        if let usage = raw["usage"] as? [String: Any] {
            for key in ["input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"] {
                if let n = int(usage[key]) { out.append(RunDetail(key: key, value: String(n))) }
            }
        }
        return out
    }

    private static func scalar(_ value: Any?) -> String? {
        switch value {
        case let s as String: return s
        case let n as NSNumber:
            if CFGetTypeID(n) == CFBooleanGetTypeID() { return n.boolValue ? "true" : "false" }
            return n.stringValue
        default: return nil
        }
    }

    /// An outcome says its own result, the finish step passes when its check did, and an agent call passes on exit 0.
    static func result(kind: String, raw: [String: Any]) -> RunResult {
        switch kind {
        case "outcome":
            switch raw["result"] as? String {
            case "done": return .pass
            case "needs-human", "stopped": return .park
            default: return .unknown
            }
        case "finish":
            return int(raw["check_exit"]).map { $0 == 0 ? .pass : .fail } ?? .unknown
        default:
            return int(raw["exit"]).map { $0 == 0 ? .pass : .fail } ?? .unknown
        }
    }

    private static func int(_ value: Any?) -> Int? {
        guard let number = value as? NSNumber, CFGetTypeID(number) != CFBooleanGetTypeID() else { return nil }
        return number.intValue
    }

    private static func double(_ value: Any?) -> Double? {
        guard let number = value as? NSNumber, CFGetTypeID(number) != CFBooleanGetTypeID() else { return nil }
        return number.doubleValue
    }

    /// The Claude Code transcript for a session: `~/.claude/projects/*/<session_id>.jsonl`.
    public static func transcript(sessionID: String, projectsDir: URL, fileManager: FileManager = .default) -> URL? {
        guard !sessionID.isEmpty, !sessionID.contains("/") else { return nil }
        let folders = (try? fileManager.contentsOfDirectory(at: projectsDir, includingPropertiesForKeys: nil)) ?? []
        return folders.lazy.map { $0.appendingPathComponent("\(sessionID).jsonl") }
            .first { fileManager.fileExists(atPath: $0.path) }
    }
}

/// Reads the runs log and the finish step's PR body off the main actor.
public struct RunsSnapshot: Equatable, Sendable {
    public let records: [RunRecord]
    public let totals: RunTotals
    public let prBody: String?

    public static let empty = RunsSnapshot(records: [], totals: RunTotals(), prBody: nil)

    public static func load(repo: URL) -> RunsSnapshot {
        let pm = repo.appendingPathComponent("_pm")
        let records = (try? Data(contentsOf: pm.appendingPathComponent("runway-runs.jsonl"))).map(RunsLog.parse) ?? []
        let body = (try? String(contentsOf: pm.appendingPathComponent("runway-pr.md"), encoding: .utf8))?
            .trimmingCharacters(in: .whitespacesAndNewlines)
        return RunsSnapshot(records: records, totals: RunsLog.totals(records), prBody: body?.isEmpty == false ? body : nil)
    }
}

extension RunwayTools {
    public func retro(repo: String) -> Command {
        Command(executable: "/usr/bin/env", arguments: ["python3", runwayScript, "--root", repo, "retro"])
    }
}
