import Foundation

private func parseISO(_ text: String) -> Date? {
    let formatter = ISO8601DateFormatter()
    if let date = formatter.date(from: text) { return date }
    formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
    return formatter.date(from: text)
}

/// `_pm/runway-state.json`, written by the loop at every phase change.
public struct Heartbeat: Equatable, Sendable {
    public let phase: String
    public let ticket: String?
    public let since: Date?
    public let pid: Int?
    /// Why a tick was skipped (phase `waiting`).
    public let reason: String?
    /// Agent attempt number during agent and check.
    public let attempt: Int?
    /// When the current tick began (`since` is when this phase began).
    public let tickStarted: Date?
    /// `pass`, `fail` or `park`: how the last ticket ended.
    public let lastResult: String?

    /// Phases that mean a tick is in flight. `idle`, `stopped`, `paused` and `waiting` are resting states.
    public static let activePhases: Set<String> = ["sync", "prep", "agent", "check", "merge", "finish"]

    public var isActive: Bool { Self.activePhases.contains(phase) }

    /// In an active phase and its process still exists. A missing `pid` can't be checked, so it counts as live.
    public func isLive(pidAlive: (Int) -> Bool) -> Bool {
        guard isActive else { return false }
        guard let pid else { return true }
        return pidAlive(pid)
    }

    /// An active phase whose process is gone: the loop died mid-ticket.
    public func isStopped(pidAlive: (Int) -> Bool) -> Bool { isActive && !isLive(pidAlive: pidAlive) }

    /// "Loop stopped during check · 17:18" for a dead tick, else nil. The time is when the phase began.
    public func stoppedDescription(timeZone: TimeZone = .current, pidAlive: (Int) -> Bool) -> String? {
        guard isStopped(pidAlive: pidAlive) else { return nil }
        guard let since else { return "Loop stopped during \(phase)" }
        let formatter = DateFormatter()
        formatter.dateFormat = "HH:mm"
        formatter.timeZone = timeZone
        return "Loop stopped during \(phase) · \(formatter.string(from: since))"
    }

    public static func parse(_ data: Data) -> Heartbeat? {
        guard let json = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any],
              let phase = json["phase"] as? String else { return nil }
        return Heartbeat(phase: phase, ticket: json["ticket"] as? String,
                         since: (json["since"] as? String).flatMap(parseISO),
                         pid: json["pid"] as? Int, reason: json["reason"] as? String,
                         attempt: json["attempt"] as? Int,
                         tickStarted: (json["tick_started"] as? String).flatMap(parseISO),
                         lastResult: json["last_result"] as? String)
    }

    public static func load(repoPath: String) -> Heartbeat? {
        let url = URL(fileURLWithPath: repoPath).appendingPathComponent("_pm/runway-state.json")
        return (try? Data(contentsOf: url)).flatMap(parse)
    }
}

/// `~/.runway/pause`: the machine-wide pause every loop honours.
public struct PauseInfo: Equatable, Sendable {
    public let until: Date?
    public let mode: String

    public init(until: Date?, mode: String) {
        self.until = until
        self.mode = mode
    }

    /// Unreadable content stays paused with no end, same as the loop (never run on a guess).
    public static func parse(_ data: Data) -> PauseInfo {
        guard let json = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any] else {
            return PauseInfo(until: nil, mode: "finish")
        }
        return PauseInfo(until: (json["until"] as? String).flatMap(parseISO), mode: (json["mode"] as? String) ?? "finish")
    }

    public func isActive(now: Date) -> Bool {
        guard let until else { return true }
        return until > now
    }

    public static var defaultURL: URL {
        let home = ProcessInfo.processInfo.environment["RUNWAY_HOME"].flatMap { $0.isEmpty ? nil : $0 }
        let dir = home.map { URL(fileURLWithPath: $0) }
            ?? FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent(".runway")
        return dir.appendingPathComponent("pause")
    }

    /// The pause in force, or nil if there is no file or it has expired.
    public static func load(_ url: URL = defaultURL, now: Date = Date()) -> PauseInfo? {
        guard let data = try? Data(contentsOf: url) else { return nil }
        let info = parse(data)
        return info.isActive(now: now) ? info : nil
    }
}

public enum RunState: Equatable, Sendable {
    case running, waiting, paused, idle, off
    case error(String)
}

/// One row of the menu: a project's state and its one-line detail.
public struct ProjectStatus: Equatable, Sendable {
    public let label: String
    public let name: String
    public let state: RunState
    public let detail: String
    /// Decisions waiting on Joe in this project.
    public let waiting: Int
}

public enum StatusResolver {
    /// Heartbeat + launchctl + pause file + decisions waiting → one state.
    /// A heartbeat in an active phase whose `pid` is gone means the tick died; that is an error, not running.
    public static func resolve(project: Project, heartbeat: Heartbeat?, pause: PauseInfo?, waiting: Int,
                               now: Date, pidAlive: (Int) -> Bool) -> ProjectStatus {
        func status(_ state: RunState, _ detail: String) -> ProjectStatus {
            ProjectStatus(label: project.label, name: project.name, state: state, detail: detail, waiting: waiting)
        }
        if let message = project.error { return status(.error(message), message) }
        guard project.loaded else { return status(.off, "loop off") }

        if let heartbeat, heartbeat.isStopped(pidAlive: pidAlive), let pid = heartbeat.pid {
            let message = "stale heartbeat (pid \(pid) not running)"
            return status(.error(message), message)
        }
        let live = heartbeat.flatMap { $0.isActive ? $0 : nil }
        if !project.running, let exit = project.lastExit, exit != 0 {
            return status(.error("exit \(exit)"), "last tick exit \(exit)")
        }
        if let pause, pause.isActive(now: now) {
            return status(.paused, "paused until " + untilText(pause.until, now: now))
        }
        if let live {
            let parts = [live.ticket, live.phase, live.since.map { age(from: $0, to: now) }]
            return status(.running, parts.compactMap { $0 }.joined(separator: " · "))
        }
        if project.running { return status(.running, "running") }
        if waiting > 0 { return status(.waiting, "\(waiting) waiting on you") }
        if let heartbeat, heartbeat.phase == "waiting", let reason = heartbeat.reason {
            return status(.idle, "waiting: \(reason)")
        }
        if let since = heartbeat?.since { return status(.idle, "idle · \(age(from: since, to: now))") }
        return status(.idle, "idle")
    }

    /// True while a process with this pid exists (EPERM means it exists but isn't ours).
    public static let systemPidAlive: @Sendable (Int) -> Bool = { pid in
        kill(pid_t(pid), 0) == 0 || errno == EPERM
    }

    /// `20s`, `6m`, `2h`, `2d`.
    public static func age(from start: Date, to now: Date) -> String {
        let seconds = max(0, Int(now.timeIntervalSince(start)))
        switch seconds {
        case ..<60: return "\(seconds)s"
        case ..<3600: return "\(seconds / 60)m"
        case ..<86400: return "\(seconds / 3600)h"
        default: return "\(seconds / 86400)d"
        }
    }

    private static func untilText(_ until: Date?, now: Date) -> String {
        guard let until else { return "resumed" }
        let formatter = DateFormatter()
        formatter.dateFormat = Calendar.current.isDate(until, inSameDayAs: now) ? "HH:mm" : "EEE HH:mm"
        return formatter.string(from: until)
    }

    /// Ticket count in `groups.waiting` of `runway status --json`.
    public static func waitingCount(statusJSON data: Data) -> Int? {
        guard let json = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any],
              let groups = json["groups"] as? [String: Any],
              let waiting = groups["waiting"] as? [Any] else { return nil }
        return waiting.count
    }
}

/// What the menu bar icon shows.
public enum OverallState: Equatable, Sendable {
    case running, waiting, paused, allOff, error

    public static func resolve(_ statuses: [ProjectStatus], pause: PauseInfo?, now: Date) -> OverallState {
        if statuses.allSatisfy({ $0.state == .off }) { return .allOff }
        if statuses.contains(where: { if case .error = $0.state { return true } else { return false } }) { return .error }
        if let pause, pause.isActive(now: now) { return .paused }
        if badge(statuses) > 0 || statuses.contains(where: { $0.state == .waiting }) { return .waiting }
        return .running
    }

    /// Decisions waiting across every project.
    public static func badge(_ statuses: [ProjectStatus]) -> Int {
        statuses.reduce(0) { $0 + $1.waiting }
    }
}
