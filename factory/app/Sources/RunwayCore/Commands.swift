import Foundation

public struct Command: Equatable, Sendable {
    public let executable: String
    public let arguments: [String]

    public init(executable: String, arguments: [String]) {
        self.executable = executable
        self.arguments = arguments
    }
}

public struct CommandResult: Equatable, Sendable {
    public let status: Int32
    public let stdout: String
    public let stderr: String

    public var succeeded: Bool { status == 0 }

    /// What to show when the command failed: its stderr, else the exit status.
    public var failureMessage: String {
        stderr.isEmpty ? "exited with status \(status)" : stderr
    }
}

public enum CommandRunner {
    /// Runs the command off the calling thread and captures both streams.
    public static func run(_ command: Command) async -> CommandResult {
        await withCheckedContinuation { continuation in
            DispatchQueue.global().async { continuation.resume(returning: runSync(command)) }
        }
    }

    static func runSync(_ command: Command) -> CommandResult {
        let process = Process()
        process.executableURL = URL(fileURLWithPath: command.executable)
        process.arguments = command.arguments
        let out = Pipe(), err = Pipe()
        process.standardOutput = out
        process.standardError = err
        process.standardInput = FileHandle.nullDevice
        do { try process.run() } catch {
            return CommandResult(status: -1, stdout: "", stderr: error.localizedDescription)
        }
        // Drain both pipes at once so a chatty command can't fill one and block.
        let errBox = DataBox()
        let group = DispatchGroup()
        group.enter()
        DispatchQueue.global().async {
            errBox.data = err.fileHandleForReading.readDataToEndOfFile()
            group.leave()
        }
        let outData = out.fileHandleForReading.readDataToEndOfFile()
        group.wait()
        process.waitUntilExit()
        func text(_ data: Data) -> String {
            String(decoding: data, as: UTF8.self).trimmingCharacters(in: .whitespacesAndNewlines)
        }
        return CommandResult(status: process.terminationStatus, stdout: text(outData), stderr: text(errBox.data))
    }

    private final class DataBox: @unchecked Sendable {
        var data = Data()
    }
}

public enum PauseChoice: Equatable, Sendable {
    case oneHour, untilTomorrow, untilResumed
}

/// Where `schedule.sh` and `runway.py` live, and the commands the menu runs with them.
public struct RunwayTools: Equatable, Sendable {
    public let scheduleScript: String
    public let runwayScript: String

    public init(scheduleScript: String, runwayScript: String) {
        self.scheduleScript = scheduleScript
        self.runwayScript = runwayScript
    }

    /// A dc-dev-plugins checkout.
    public init(checkout: String) {
        let experiments = URL(fileURLWithPath: checkout).appendingPathComponent("factory/experiments")
        self.init(scheduleScript: experiments.appendingPathComponent("03-linear/schedule.sh").path,
                  runwayScript: experiments.appendingPathComponent("01-runway/runway.py").path)
    }

    /// The `runway.py` a LaunchAgent plist points at; `schedule.sh` is its sibling under `experiments/`.
    public init(runwayScript: String) {
        let experiments = URL(fileURLWithPath: runwayScript).deletingLastPathComponent().deletingLastPathComponent()
        self.init(scheduleScript: experiments.appendingPathComponent("03-linear/schedule.sh").path,
                  runwayScript: runwayScript)
    }

    /// The checkout from the setting if there is one, else the one the first plist points at.
    public static func locate(checkoutSetting: String?, projects: [Project]) -> RunwayTools? {
        if let checkoutSetting, !checkoutSetting.isEmpty { return RunwayTools(checkout: checkoutSetting) }
        return projects.lazy.compactMap(\.runwayScript).first.map { RunwayTools(runwayScript: $0) }
    }

    public func start(repo: String, minutes: Int) -> Command {
        Command(executable: "/bin/bash", arguments: [scheduleScript, "install", repo, String(minutes)])
    }

    public func stop(repo: String) -> Command {
        Command(executable: "/bin/bash", arguments: [scheduleScript, "uninstall", repo])
    }

    public static func runNow(label: String, uid: UInt32 = getuid()) -> Command {
        Command(executable: "/bin/launchctl", arguments: ["kickstart", "gui/\(uid)/\(label)"])
    }

    public func status(repo: String) -> Command {
        Command(executable: "/usr/bin/env", arguments: ["python3", runwayScript, "--root", repo, "status", "--json"])
    }

    public func pause(_ choice: PauseChoice, now: Date = Date(), calendar: Calendar = .current) -> Command {
        var args = ["python3", runwayScript, "pause"]
        switch choice {
        case .oneHour: args += ["--for", "1h"]
        case .untilTomorrow:
            args += ["--until", Self.isoLocal(Self.nextEightAM(after: now, calendar: calendar), calendar: calendar)]
        case .untilResumed: break
        }
        return Command(executable: "/usr/bin/env", arguments: args)
    }

    /// `runway go|no <ticket> "<note>"`. The note is one argument; a leading dash goes after `--` so argparse can't read it as an option.
    public func answer(go: Bool, ticket: String, note: String, repo: String) -> Command {
        var args = ["python3", runwayScript, "--root", repo, go ? "go" : "no", ticket]
        if note.hasPrefix("-") { args.append("--") }
        args.append(note)
        return Command(executable: "/usr/bin/env", arguments: args)
    }

    public func resume() -> Command {
        Command(executable: "/usr/bin/env", arguments: ["python3", runwayScript, "resume"])
    }

    /// The next 08:00 after `date`: this morning if it is still before 08:00, else tomorrow's.
    public static func nextEightAM(after date: Date, calendar: Calendar) -> Date {
        calendar.nextDate(after: date, matching: DateComponents(hour: 8, minute: 0, second: 0),
                          matchingPolicy: .nextTime) ?? date.addingTimeInterval(24 * 3600)
    }

    /// ISO-8601 in the calendar's zone with its offset, the form `runway pause --until` takes.
    public static func isoLocal(_ date: Date, calendar: Calendar) -> String {
        let formatter = ISO8601DateFormatter()
        formatter.timeZone = calendar.timeZone
        return formatter.string(from: date)
    }
}
