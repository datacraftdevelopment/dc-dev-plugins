import Foundation
import Observation

/// One ticket in `runway status --json`.
public struct QueueTicket: Equatable, Sendable, Identifiable {
    public let id: String
    public let title: String
    public let url: String?
    public let status: String
    public let gate: String
    public let blockedBy: [String]
    public let waitingOn: String?
    public let harness: String?
    /// The decision packet (Markdown) for a waiting ticket; nil for any other.
    public let packet: String?
    /// Kind of the ticket's latest attempt that didn't merge (`check-failed`…); nil when not errored or the engine is older.
    public var errored: String?
    /// Why the ticket is where it is (the engine's `reason`); nil from an older engine.
    public var reason: String? = nil
    /// What the queue plan does with it (`run`, `queued`, `prep`, `park`, `waiting`, `blocked`…); nil from an older engine.
    public var nextStep: String? = nil
    /// The latest attempt was a claude session the engine can reopen (`discuss --resume`), a done ticket's too;
    /// false from an older engine.
    public var resumable = false
}

public struct QueueSections: Equatable, Sendable {
    /// Running now, then ready-to-run in the order `tick` takes them.
    public let runsNext: [QueueTicket]
    /// Needs a decision, or needs prep by a person.
    public let waiting: [QueueTicket]
    public let blocked: [QueueTicket]
    public let done: [QueueTicket]
}

/// The finish verdict from status: `finish`, `wait` or `off`, and why.
public struct QueueFinish: Equatable, Sendable {
    public let verdict: String
    public let reason: String
}

/// The one banner over the board: what runs next (or why nothing does) and where finish stands.
public struct QueueBanner: Equatable, Sendable {
    public let headline: String?
    public let finish: String?
}

/// The `status --json` document (version 1), as far as the board reads it.
public struct QueueStatus: Equatable, Sendable {
    public let tickets: [QueueTicket]
    let groups: [String: [String]]
    /// The last finish review was a claude session `discuss --review` can reopen; false from an older engine.
    public var reviewResumable = false
    /// That review's session id, so a pane left open on an older review isn't mistaken for this one.
    public var reviewSession: String? = nil
    /// The ticket the next tick would run; nil when nothing can run, or from an older engine.
    public var runNow: String? = nil
    /// One line on why nothing runs, when `runNow` is nil.
    public var idleReason: String? = nil
    public var finish: QueueFinish? = nil
    /// The engine sent the queue plan (it always writes `run_now`, null or not). False from an older engine.
    public var hasPlan = false

    /// The banner text. Nil from an older engine that sends no plan fields.
    public var banner: QueueBanner? {
        guard hasPlan || finish != nil else { return nil }
        var headline: String? = idleReason
        if let id = runNow {
            let title = tickets.first { $0.id == id }?.title ?? ""
            headline = "Runs next: " + (title.isEmpty ? id : "\(id) \(title)")
        }
        let finishLine = finish.map { f -> String in
            let word = f.verdict == "wait" ? "waits" : f.verdict
            return f.reason.isEmpty ? "Finish \(word)" : "Finish \(word): \(f.reason)"
        }
        return QueueBanner(headline: headline, finish: finishLine)
    }

    /// Ticket ids in one of status's groups (`waiting`, `running`, `ready_auto`, `ready_prep`, `blocked`, `done`), in queue order.
    public func group(_ key: String) -> [String] { groups[key] ?? [] }

    public static func parse(_ data: Data) -> QueueStatus? {
        guard let root = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any],
              (root["version"] as? Int) == 1,
              let rawGroups = root["groups"] as? [String: Any],
              let rawTickets = root["tickets"] as? [[String: Any]] else { return nil }
        let tickets = rawTickets.compactMap { raw -> QueueTicket? in
            guard let id = raw["id"] as? String else { return nil }
            return QueueTicket(id: id, title: raw["title"] as? String ?? "", url: raw["url"] as? String,
                               status: raw["status"] as? String ?? "", gate: raw["gate"] as? String ?? "",
                               blockedBy: raw["blocked_by"] as? [String] ?? [],
                               waitingOn: raw["waiting_on"] as? String, harness: raw["harness"] as? String,
                               packet: raw["packet"] as? String,
                               errored: (raw["errored"] as? String).flatMap { $0.isEmpty ? nil : $0 },
                               reason: (raw["reason"] as? String).flatMap { $0.isEmpty ? nil : $0 },
                               nextStep: (raw["next_step"] as? String).flatMap { $0.isEmpty ? nil : $0 },
                               resumable: raw["resumable"] as? Bool ?? false)
        }
        var groups: [String: [String]] = [:]
        for (key, value) in rawGroups { groups[key] = value as? [String] ?? [] }
        let finish = (root["finish"] as? [String: Any]).flatMap { raw -> QueueFinish? in
            guard let verdict = raw["verdict"] as? String else { return nil }
            return QueueFinish(verdict: verdict, reason: raw["reason"] as? String ?? "")
        }
        return QueueStatus(tickets: tickets, groups: groups, reviewResumable: root["review_resumable"] as? Bool ?? false,
                           reviewSession: root["review_session"] as? String,
                           runNow: root["run_now"] as? String,
                           idleReason: (root["idle_reason"] as? String).flatMap { $0.isEmpty ? nil : $0 },
                           finish: finish, hasPlan: root.keys.contains("run_now"))
    }

    /// Tickets waiting on a go or no (the `waiting` group, not tickets that merely need prep).
    public var decisions: [QueueTicket] {
        let byID = Dictionary(tickets.map { ($0.id, $0) }, uniquingKeysWith: { first, _ in first })
        return (groups["waiting"] ?? []).compactMap { byID[$0] }
    }

    public var sections: QueueSections {
        let byID = Dictionary(tickets.map { ($0.id, $0) }, uniquingKeysWith: { first, _ in first })
        func pick(_ keys: String...) -> [QueueTicket] {
            keys.flatMap { groups[$0] ?? [] }.compactMap { byID[$0] }
        }
        return QueueSections(runsNext: pick("running", "ready_auto"), waiting: pick("waiting", "ready_prep"),
                             blocked: pick("blocked"), done: pick("done"))
    }
}

/// Runs `runway status --json` off the main actor and keeps the last good answer, so a failed call
/// (no network, bad key) shows its error beside the old queue and the old queue's age.
@MainActor @Observable
public final class QueueFeed {
    public private(set) var queue: QueueStatus?
    /// When `queue` was fetched; nil before the first good fetch.
    public private(set) var fetchedAt: Date?
    public private(set) var error: String?
    public private(set) var isRefreshing = false

    @ObservationIgnored private let run: @Sendable (Command) async -> CommandResult
    @ObservationIgnored private let now: @Sendable () -> Date

    public init(run: @escaping @Sendable (Command) async -> CommandResult = { await CommandRunner.run($0) },
                now: @escaping @Sendable () -> Date = { Date() }) {
        self.run = run
        self.now = now
    }

    /// Suspends while the command runs, so the main actor stays free. A refresh already under way wins.
    public func refresh(_ command: Command) async {
        guard !isRefreshing else { return }
        isRefreshing = true
        defer { isRefreshing = false }
        let result = await run(command)
        if !result.succeeded {
            error = result.failureMessage
        } else if let parsed = QueueStatus.parse(Data(result.stdout.utf8)) {
            queue = parsed
            fetchedAt = now()
            error = nil
        } else {
            error = "Couldn't read the status output."
        }
    }

    public nonisolated static func ageText(from date: Date, now: Date) -> String {
        let seconds = Int(now.timeIntervalSince(date))
        if seconds < 60 { return "just now" }
        if seconds < 3600 { return "\(seconds / 60)m ago" }
        return "\(seconds / 3600)h ago"
    }
}
