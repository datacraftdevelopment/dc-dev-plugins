import Foundation

public enum NextTick: Equatable, Sendable {
    /// Loop is off: nothing is scheduled.
    case none
    /// Loop is on but there is no last run (never ran) or no interval to count from.
    case unknown
    case due
    case at(Date)
}

public enum NowBanner: Equatable, Sendable {
    case loopOffReady(Int)
    case decisionsWaiting(Int)
    case paused
}

public struct PhaseStep: Equatable, Sendable {
    public enum State: Equatable, Sendable { case done, current, todo }
    public let name: String
    public let state: State
}

/// The Now tab's arithmetic, kept out of the views so it can be tested.
public enum NowMath {
    public static let phases = ["sync", "prep", "agent", "check", "merge"]

    /// Seconds since the current tick began, or nil when no tick is in flight.
    public static func elapsed(heartbeat: Heartbeat?, now: Date) -> TimeInterval? {
        guard let heartbeat, heartbeat.isActive, let start = heartbeat.tickStarted ?? heartbeat.since else { return nil }
        return max(0, now.timeIntervalSince(start))
    }

    /// `m:ss`, or `h:mm:ss` from an hour up.
    public static func clock(_ seconds: TimeInterval) -> String {
        let total = max(0, Int(seconds))
        let h = total / 3600, m = total % 3600 / 60, s = total % 60
        return h > 0 ? String(format: "%d:%02d:%02d", h, m, s) : String(format: "%d:%02d", m, s)
    }

    /// Last run + StartInterval.
    public static func nextTick(lastRun: Date?, interval: Int?, loopOn: Bool, now: Date) -> NextTick {
        guard loopOn else { return .none }
        guard let lastRun, let interval, interval > 0 else { return .unknown }
        let next = lastRun.addingTimeInterval(TimeInterval(interval))
        return next > now ? .at(next) : .due
    }

    public static func text(_ next: NextTick, now: Date) -> String {
        switch next {
        case .none: return "loop off"
        case .unknown: return "—"
        case .due: return "due now"
        case .at(let date): return "in " + clock(date.timeIntervalSince(now))
        }
    }

    /// Done / current / todo for sync → prep → agent → check → merge. `finish` comes after merge, so all are done.
    public static func phaseStrip(heartbeat: Heartbeat?) -> [PhaseStep] {
        var current: Int?
        if let heartbeat, heartbeat.isActive {
            current = heartbeat.phase == "finish" ? phases.count : phases.firstIndex(of: heartbeat.phase)
        }
        return phases.enumerated().map { index, name in
            guard let current else { return PhaseStep(name: name, state: .todo) }
            return PhaseStep(name: name, state: index < current ? .done : index == current ? .current : .todo)
        }
    }

    public static func banners(loopOn: Bool, readyCount: Int, waiting: Int, paused: Bool) -> [NowBanner] {
        var banners: [NowBanner] = []
        if !loopOn, readyCount > 0 { banners.append(.loopOffReady(readyCount)) }
        if waiting > 0 { banners.append(.decisionsWaiting(waiting)) }
        if paused { banners.append(.paused) }
        return banners
    }
}

/// The last lines of a log, read incrementally: each `poll` reads only the bytes appended since the last one.
/// A file that is missing is empty; one that shrank (rotated or replaced) is read again from its tail.
public struct LogTail: Sendable {
    /// How far back from the end the first read looks, so a huge log is never read whole.
    public static let initialWindow = 64 * 1024

    public let url: URL
    public let maxLines: Int
    public private(set) var lines: [String] = []
    /// Bytes read by the last `poll`.
    public private(set) var bytesRead = 0
    private var offset: UInt64 = 0
    private var started = false
    private var partial = Data()

    public init(url: URL, maxLines: Int = 30) {
        self.url = url
        self.maxLines = maxLines
    }

    /// True when `lines` changed.
    @discardableResult
    public mutating func poll() -> Bool {
        bytesRead = 0
        guard let handle = try? FileHandle(forReadingFrom: url) else {
            let changed = !lines.isEmpty
            self = LogTail(url: url, maxLines: maxLines)
            return changed
        }
        defer { try? handle.close() }
        guard let size = try? handle.seekToEnd() else { return false }

        var skipFirstLine = false
        var changed = false
        if !started || size < offset {
            changed = !lines.isEmpty
            lines = []
            partial = Data()
            let start = size > UInt64(Self.initialWindow) ? size - UInt64(Self.initialWindow) : 0
            skipFirstLine = start > 0  // landed mid-line
            offset = start
            started = true
        } else if size == offset {
            return false
        }

        guard (try? handle.seek(toOffset: offset)) != nil,
              let data = try? handle.readToEnd(), !data.isEmpty else { return changed }
        bytesRead = data.count
        offset += UInt64(data.count)

        var buffer = partial + data
        if skipFirstLine {
            guard let newline = buffer.firstIndex(of: 0x0A) else { partial = Data(); return changed }
            buffer = Data(buffer[buffer.index(after: newline)...])
        }
        var pieces = buffer.split(separator: 0x0A, omittingEmptySubsequences: false)
        partial = Data(pieces.removeLast())  // text after the last newline: an unfinished line
        let complete = pieces.map { String(decoding: $0, as: UTF8.self) }
        guard !complete.isEmpty else { return changed }
        lines = Array((lines + complete).suffix(maxLines))
        return true
    }
}

/// One row of `_pm/runway.log` as the Now tab shows it. A run of identical idle lines is one row with a count.
public struct LogEntry: Equatable, Sendable {
    /// `HH:mm` of the first line, or nil for a line that isn't a timestamped event (a continuation line).
    public let time: String?
    /// `HH:mm` of the last line folded into this row, when there was more than one.
    public let until: String?
    /// The event word (one of `LogFeed.kinds`), or empty for any other line.
    public let kind: String
    public let text: String
    public let count: Int
}

public enum LogFeed {
    /// The words `runway.py` starts an event line with. Any other line ("Ready for review: …") is plain text.
    public static let kinds: Set<String> = ["idle", "prep", "sync", "run", "fail", "done", "finish", "review",
                                            "pr", "park", "skip", "answer"]

    /// Parses `YYYY-MM-DD HH:mm TZ  kind  text` lines; anything else is kept as a continuation line.
    /// Consecutive `idle` lines with the same text fold into one entry.
    public static func entries(_ lines: [String]) -> [LogEntry] {
        var out: [LogEntry] = []
        for line in lines where !line.trimmingCharacters(in: .whitespaces).isEmpty {
            guard let parsed = parse(line) else {
                out.append(LogEntry(time: nil, until: nil, kind: "", text: line.trimmingCharacters(in: .whitespaces), count: 1))
                continue
            }
            if parsed.kind == "idle", let last = out.last, last.kind == "idle", last.text == parsed.text {
                out[out.count - 1] = LogEntry(time: last.time, until: parsed.time, kind: "idle", text: last.text,
                                              count: last.count + 1)
            } else {
                out.append(LogEntry(time: parsed.time, until: nil, kind: parsed.kind, text: parsed.text, count: 1))
            }
        }
        return out
    }

    private static func parse(_ line: String) -> (time: String, kind: String, text: String)? {
        let parts = line.split(separator: " ", maxSplits: 3, omittingEmptySubsequences: true)
        guard parts.count >= 4, parts[0].count == 10, parts[0].allSatisfy({ $0.isNumber || $0 == "-" }),
              parts[1].count == 5, parts[1].contains(":") else { return nil }
        let rest = parts[3].trimmingCharacters(in: .whitespaces)
        let split = rest.split(separator: " ", maxSplits: 1, omittingEmptySubsequences: true)
        guard let first = split.first.map(String.init), kinds.contains(first) else { return (String(parts[1]), "", rest) }
        let text = split.count > 1 ? split[1].trimmingCharacters(in: .whitespaces) : ""
        return (String(parts[1]), first, text)
    }
}
