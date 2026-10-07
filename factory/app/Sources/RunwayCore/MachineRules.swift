import Foundation

// This Mac's quiet-time rules: `~/.runway/machine.json`, the file `runway.py` reads at the start of every tick.
// The app edits the keys it knows and keeps every other key as it found it.

public struct MachineRules: Equatable, Sendable {
    public enum PauseMode: String, Equatable, Sendable, CaseIterable {
        /// Let the running ticket finish; nothing new starts.
        case finish
        /// Also stop the running agent now.
        case stop
    }

    public static let allDays = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

    public var quietEnabled = false
    public var quietFrom = "09:00"
    public var quietTo = "17:00"
    public var quietDays = MachineRules.allDays
    public var idleEnabled = false
    public var idleMinutes = 10
    public var notOnBattery = false
    /// 0 is no limit (the key is left out of the file).
    public var maxAgents = 0
    public var pauseMode = PauseMode.finish

    public init() {}

    /// `HH:mm`, 24-hour, two digits each: the form the engine's `time.fromisoformat` reads.
    public static func isValidTime(_ text: String) -> Bool {
        text.range(of: #"^([01][0-9]|2[0-3]):[0-5][0-9]$"#, options: .regularExpression) != nil
    }

    /// What is wrong with the rules, in the words the sheet shows. Save is refused while this isn't empty.
    public var problems: [String] {
        var found: [String] = []
        if quietEnabled {
            if !Self.isValidTime(quietFrom) { found.append("Quiet hours start must be a time like 09:00.") }
            if !Self.isValidTime(quietTo) { found.append("Quiet hours end must be a time like 17:00.") }
            if quietDays.isEmpty { found.append("Pick at least one day for quiet hours.") }
        }
        if idleEnabled, idleMinutes < 1 { found.append("Idle time must be at least 1 minute.") }
        if maxAgents < 0 { found.append("Max agents can't be negative.") }
        return found
    }
}

public enum MachineFile {
    struct Failure: LocalizedError {
        let errorDescription: String?
    }

    /// The top-level object of an existing file, or nil if it isn't one.
    static func existingObject(_ data: Data) -> [String: Any]? {
        (try? JSONSerialization.jsonObject(with: data)) as? [String: Any]
    }

    public static func decode(_ data: Data) throws -> MachineRules {
        guard let json = existingObject(data) else { throw Failure(errorDescription: "machine.json isn't a JSON object.") }
        var rules = MachineRules()
        if let quiet = json["quiet_hours"] as? [String: Any] {
            rules.quietEnabled = quiet["enabled"] as? Bool ?? false
            rules.quietFrom = quiet["from"] as? String ?? rules.quietFrom
            rules.quietTo = quiet["to"] as? String ?? rules.quietTo
            if let days = quiet["days"] as? [String] { rules.quietDays = days.map { String($0.lowercased().prefix(3)) } }
        }
        if let idle = json["idle_only"] as? [String: Any] {
            rules.idleEnabled = idle["enabled"] as? Bool ?? false
            rules.idleMinutes = (idle["minutes"] as? NSNumber)?.intValue ?? rules.idleMinutes
        }
        rules.notOnBattery = json["not_on_battery"] as? Bool ?? false
        rules.maxAgents = (json["max_agents"] as? NSNumber)?.intValue ?? 0
        rules.pauseMode = (json["pause_mode"] as? String).flatMap(MachineRules.PauseMode.init(rawValue:)) ?? .finish
        return rules
    }

    /// The file's bytes for `rules`, laid over `existing` so keys this app doesn't know survive, at the top
    /// level and inside `quiet_hours` and `idle_only`.
    public static func encode(_ rules: MachineRules, over existing: Data?) -> Data {
        var json = existing.flatMap(existingObject) ?? [:]
        var quiet = json["quiet_hours"] as? [String: Any] ?? [:]
        quiet["enabled"] = rules.quietEnabled
        quiet["from"] = rules.quietFrom
        quiet["to"] = rules.quietTo
        quiet["days"] = rules.quietDays
        var idle = json["idle_only"] as? [String: Any] ?? [:]
        idle["enabled"] = rules.idleEnabled
        idle["minutes"] = rules.idleMinutes
        json["version"] = json["version"] ?? 1
        json["quiet_hours"] = quiet
        json["idle_only"] = idle
        json["not_on_battery"] = rules.notOnBattery
        json["max_agents"] = rules.maxAgents > 0 ? rules.maxAgents : nil
        json["pause_mode"] = rules.pauseMode.rawValue
        // Sorted keys keep the file stable under version control and easy to diff by hand.
        return (try? JSONSerialization.data(withJSONObject: json, options: [.prettyPrinted, .sortedKeys])) ?? Data()
    }
}

/// `~/.runway/machine.json` on disk.
public struct MachineStore: Sendable {
    public let home: URL

    public init(home: URL = MachineStore.defaultHome) {
        self.home = home
    }

    /// `$RUNWAY_HOME` if set, as the engine does, else `~/.runway`.
    public static var defaultHome: URL {
        if let path = ProcessInfo.processInfo.environment["RUNWAY_HOME"], !path.isEmpty { return URL(fileURLWithPath: path) }
        return FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent(".runway")
    }

    public var url: URL { home.appendingPathComponent("machine.json") }

    private func existing() throws -> Data? {
        do { return try Data(contentsOf: url) } catch CocoaError.fileReadNoSuchFile { return nil }
    }

    /// A missing file is no rules. An unreadable one throws.
    public func load() throws -> MachineRules {
        guard let data = try existing() else { return MachineRules() }
        return try MachineFile.decode(data)
    }

    /// Writes the file atomically. Refuses invalid rules, and refuses to replace a file it can't read, since that
    /// would throw away whatever it holds.
    public func save(_ rules: MachineRules) throws {
        if let first = rules.problems.first { throw MachineFile.Failure(errorDescription: first) }
        let current = try existing()
        if let current, MachineFile.existingObject(current) == nil {
            throw MachineFile.Failure(errorDescription: "machine.json isn't readable, so it was left alone. Fix or delete it first.")
        }
        try FileManager.default.createDirectory(at: home, withIntermediateDirectories: true)
        try MachineFile.encode(rules, over: current).write(to: url, options: .atomic)
    }
}

extension RunwayTools {
    /// `runway machine`: the rules, and whether a tick would run now or why not.
    public func machine() -> Command {
        Command(executable: "/usr/bin/env", arguments: ["python3", runwayScript, "machine"])
    }
}
