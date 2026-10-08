import Foundation

/// This Mac's quiet window from `~/.runway/machine.json`. Same rules as the engine's `in_quiet_hours`:
/// `days` are the days a window starts on, so an overnight window belongs to the day it began.
public struct QuietHours: Equatable, Sendable {
    public static let allDays = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

    public let from: String
    public let to: String
    public let days: [String]

    public init(from: String, to: String, days: [String]) {
        self.from = from
        self.to = to
        self.days = days
    }

    /// The enabled quiet window in machine.json, else nil (no file content, disabled, or no window).
    public static func parse(_ data: Data) -> QuietHours? {
        guard let json = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any],
              let q = json["quiet_hours"] as? [String: Any],
              q["enabled"] as? Bool == true,
              let from = q["from"] as? String, let to = q["to"] as? String else { return nil }
        let days = (q["days"] as? [String])?.map { String($0.lowercased().prefix(3)) } ?? allDays
        return QuietHours(from: from, to: to, days: days)
    }

    public static var defaultURL: URL {
        PauseInfo.defaultURL.deletingLastPathComponent().appendingPathComponent("machine.json")
    }

    /// The window in force. An unreadable file counts as quiet (never nag on a guess); a missing one as none.
    public static func load(_ url: URL = defaultURL) -> QuietHours? {
        guard let data = try? Data(contentsOf: url) else { return nil }
        if (try? JSONSerialization.jsonObject(with: data)) as? [String: Any] == nil {
            return QuietHours(from: "00:00", to: "00:00", days: allDays)
        }
        return parse(data)
    }

    private static func minutes(_ text: String) -> Int? {
        let parts = text.split(separator: ":").compactMap { Int($0) }
        guard parts.count >= 2, (0..<24).contains(parts[0]), (0..<60).contains(parts[1]) else { return nil }
        return parts[0] * 60 + parts[1]
    }

    public func contains(_ date: Date, calendar: Calendar = .current) -> Bool {
        // Unparseable times: quiet, same reasoning as an unreadable file.
        guard let start = Self.minutes(from), let end = Self.minutes(to) else { return true }
        let parts = calendar.dateComponents([.weekday, .hour, .minute], from: date)
        let names = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"]
        let index = (parts.weekday ?? 1) - 1
        let today = names[index], yesterday = names[(index + 6) % 7]
        let t = (parts.hour ?? 0) * 60 + (parts.minute ?? 0)
        if start == end { return days.contains(today) }
        if start < end { return days.contains(today) && start <= t && t < end }
        return (t >= start && days.contains(today)) || (t < end && days.contains(yesterday))
    }
}

/// What one project's `runway status --json` said, reduced to what notifications need.
public struct StatusSnapshot: Equatable, Sendable {
    public struct Ticket: Equatable, Sendable {
        public let id: String
        public let title: String
        public let status: String
        public let gate: String

        public init(id: String, title: String, status: String, gate: String) {
            self.id = id
            self.title = title
            self.status = status
            self.gate = gate
        }
    }

    /// Tickets waiting on Joe (`needs-human`).
    public let tickets: [Ticket]
    /// Tickets the loop could pick up: `ready_auto` plus `ready_prep`.
    public let readyCount: Int

    /// Every ticket's title by id, so the Now tab can name what the loop is working on.
    public let titles: [String: String]
    /// Each ticket's tracker link (a Linear issue URL) by id, when the tracker gives one.
    public let urls: [String: URL]

    public init(tickets: [Ticket], readyCount: Int, titles: [String: String] = [:], urls: [String: URL] = [:]) {
        self.tickets = tickets
        self.readyCount = readyCount
        self.titles = titles
        self.urls = urls
    }

    public static func parse(_ data: Data) -> StatusSnapshot? {
        guard let json = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any],
              let groups = json["groups"] as? [String: Any] else { return nil }
        func count(_ key: String) -> Int { (groups[key] as? [Any])?.count ?? 0 }
        let waiting = Set((groups["waiting"] as? [String]) ?? [])
        let all = (json["tickets"] as? [[String: Any]]) ?? []
        let tickets = all.compactMap { entry -> Ticket? in
            guard let id = entry["id"] as? String, waiting.contains(id) else { return nil }
            return Ticket(id: id, title: (entry["title"] as? String) ?? "", status: (entry["status"] as? String) ?? "needs-human",
                          gate: (entry["gate"] as? String) ?? "")
        }
        var titles: [String: String] = [:]
        var urls: [String: URL] = [:]
        for entry in all {
            guard let id = entry["id"] as? String else { continue }
            titles[id] = entry["title"] as? String
            if let link = entry["url"] as? String, link.hasPrefix("https://"), let url = URL(string: link) { urls[id] = url }
        }
        return StatusSnapshot(tickets: tickets, readyCount: count("ready_auto") + count("ready_prep"), titles: titles,
                              urls: urls)
    }
}

/// One project at one moment. `status` is nil when the last status call failed.
public struct ProjectSnapshot: Equatable, Sendable {
    public let label: String
    public let name: String
    public let loopOn: Bool
    public let status: StatusSnapshot?

    public init(label: String, name: String, loopOn: Bool, status: StatusSnapshot?) {
        self.label = label
        self.name = name
        self.loopOn = loopOn
        self.status = status
    }

    public var readyWhileOff: Bool { !loopOn && (status?.readyCount ?? 0) > 0 }

    /// Drives the amber menu bar icon. Independent of notifications and of quiet hours.
    public static func readyWhileOff(_ snapshots: [ProjectSnapshot]) -> Bool {
        snapshots.contains(where: \.readyWhileOff)
    }
}

public enum NotificationTab: String, Equatable, Sendable {
    case decisions, projects
}

/// Where a click on a notification goes.
public struct NotificationRoute: Equatable, Sendable {
    public let projectLabel: String
    public let ticketID: String?
    public let tab: NotificationTab

    public init(projectLabel: String, ticketID: String?, tab: NotificationTab) {
        self.projectLabel = projectLabel
        self.ticketID = ticketID
        self.tab = tab
    }

    public init?(userInfo: [AnyHashable: Any]) {
        guard let label = userInfo["project"] as? String,
              let tab = (userInfo["tab"] as? String).flatMap(NotificationTab.init(rawValue:)) else { return nil }
        self.init(projectLabel: label, ticketID: userInfo["ticket"] as? String, tab: tab)
    }
}

public struct NotificationEvent: Equatable, Sendable {
    public enum Kind: String, Equatable, Sendable { case decision, parked, idleReady }

    public let kind: Kind
    public let projectLabel: String
    public let ticketID: String?
    public let title: String
    public let body: String

    public var route: NotificationRoute {
        NotificationRoute(projectLabel: projectLabel, ticketID: ticketID, tab: kind == .idleReady ? .projects : .decisions)
    }

    public var userInfo: [AnyHashable: Any] {
        var info: [AnyHashable: Any] = ["project": route.projectLabel, "tab": route.tab.rawValue]
        if let ticketID { info["ticket"] = ticketID }
        return info
    }

    /// Stable id, so a delivered notification replaces rather than stacks.
    public var identifier: String {
        "runway.\(kind.rawValue).\(projectLabel)" + (ticketID.map { ".\($0)" } ?? "")
    }
}

/// What was already notified, so a restart doesn't repeat it. Lives in Application Support.
public struct NotificationLedger: Equatable, Codable, Sendable {
    public var entries: [String: Date]

    public init(entries: [String: Date] = [:]) { self.entries = entries }

    public static var defaultURL: URL {
        let base = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first
            ?? FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Application Support")
        return base.appendingPathComponent("Runway/notified.json")
    }

    /// A missing or unreadable file is an empty ledger.
    public static func load(from url: URL = defaultURL) -> NotificationLedger {
        guard let data = try? Data(contentsOf: url) else { return NotificationLedger() }
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        return (try? decoder.decode(NotificationLedger.self, from: data)) ?? NotificationLedger()
    }

    public func save(to url: URL = defaultURL) throws {
        try FileManager.default.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        encoder.outputFormatting = [.sortedKeys, .prettyPrinted]
        try encoder.encode(self).write(to: url, options: .atomic)
    }
}

/// The "should notify" decision. Default cadence (DAT-19): once per decision packet, once per ticket parked
/// after a failed retry, and once per project with ready tickets but its loop off, at most every 4 hours and
/// never in quiet hours. Decisions and parked tickets are not held back by quiet hours: they are rare and
/// they are the point of the app.
public enum NotificationPlanner {
    public static let idleRepeat: TimeInterval = 4 * 3600

    /// Returns what to notify now and the ledger to persist. Persist the ledger before delivering.
    public static func plan(_ projects: [ProjectSnapshot], ledger: NotificationLedger, now: Date,
                            quiet: QuietHours?, calendar: Calendar = .current)
        -> (events: [NotificationEvent], ledger: NotificationLedger) {
        var ledger = ledger
        var events: [NotificationEvent] = []
        let inQuiet = quiet?.contains(now, calendar: calendar) ?? false

        for project in projects {
            guard let status = project.status else { continue }  // no answer: keep what we remember

            var live = Set<String>()
            for ticket in status.tickets {
                // A human-gated ticket waits on its decision packet; any other waiting ticket was parked after a failed retry.
                let kind: NotificationEvent.Kind = ticket.gate == "human" ? .decision : .parked
                let key = "\(kind.rawValue):\(project.label):\(ticket.id)"
                live.insert(key)
                guard ledger.entries[key] == nil else { continue }
                ledger.entries[key] = now
                let what = kind == .decision ? "Decision waiting" : "Parked, needs you"
                events.append(NotificationEvent(
                    kind: kind, projectLabel: project.label, ticketID: ticket.id,
                    title: "\(project.name): \(what)",
                    body: ticket.title.isEmpty ? ticket.id : "\(ticket.id) \(ticket.title)"))
            }
            // Answered tickets drop out, so a later park of the same ticket notifies again.
            for key in ledger.entries.keys where isTicketKey(key, project: project.label) && !live.contains(key) {
                ledger.entries[key] = nil
            }

            if project.readyWhileOff, !inQuiet {
                let key = "idle:\(project.label)"
                if ledger.entries[key].map({ now.timeIntervalSince($0) >= idleRepeat }) ?? true {
                    ledger.entries[key] = now
                    let n = status.readyCount
                    events.append(NotificationEvent(
                        kind: .idleReady, projectLabel: project.label, ticketID: nil,
                        title: "\(project.name): ready work, loop is off",
                        body: "\(n) ticket\(n == 1 ? "" : "s") ready for an agent. Start the loop to pick them up."))
                }
            }
        }
        return (events, ledger)
    }

    private static func isTicketKey(_ key: String, project: String) -> Bool {
        key.hasPrefix("decision:\(project):") || key.hasPrefix("parked:\(project):")
    }
}
