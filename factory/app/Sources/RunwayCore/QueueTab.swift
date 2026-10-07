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
}

public struct QueueSections: Equatable, Sendable {
    /// Running now, then ready-to-run in the order `tick` takes them.
    public let runsNext: [QueueTicket]
    /// Needs a decision, or needs prep by a person.
    public let waiting: [QueueTicket]
    public let blocked: [QueueTicket]
    public let done: [QueueTicket]
}

/// The `status --json` document (version 1), as far as the Queue tab reads it.
public struct QueueStatus: Equatable, Sendable {
    public let tickets: [QueueTicket]
    let groups: [String: [String]]

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
                               waitingOn: raw["waiting_on"] as? String, harness: raw["harness"] as? String)
        }
        var groups: [String: [String]] = [:]
        for (key, value) in rawGroups { groups[key] = value as? [String] ?? [] }
        return QueueStatus(tickets: tickets, groups: groups)
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
