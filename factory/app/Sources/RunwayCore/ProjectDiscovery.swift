import Foundation

/// What `schedule.sh install` writes into a LaunchAgent plist.
public struct LaunchJob: Equatable, Sendable {
    public let label: String
    public let repoPath: String
    public let interval: Int?
    public let logPath: String?

    public enum ParseError: Error, Equatable {
        case notAPlist
        case missingLabel
        case missingRoot
    }

    public static func parse(plist data: Data) throws -> LaunchJob {
        guard let dict = (try? PropertyListSerialization.propertyList(from: data, format: nil)) as? [String: Any] else {
            throw ParseError.notAPlist
        }
        guard let label = dict["Label"] as? String else { throw ParseError.missingLabel }
        let args = (dict["ProgramArguments"] as? [String]) ?? []
        guard let root = args.lazy.compactMap(rootArgument).first else { throw ParseError.missingRoot }
        return LaunchJob(
            label: label,
            repoPath: root,
            interval: dict["StartInterval"] as? Int,
            logPath: dict["StandardOutPath"] as? String)
    }

    /// `--root "/path with spaces"` or `--root /path` inside the shell command string.
    private static func rootArgument(_ arg: String) -> String? {
        if arg == "--root" { return nil }
        guard let range = arg.range(of: "--root ") else { return nil }
        let rest = arg[range.upperBound...].drop(while: { $0 == " " })
        if rest.first == "\"" {
            let body = rest.dropFirst()
            guard let end = body.firstIndex(of: "\"") else { return nil }
            return String(body[..<end])
        }
        let path = rest.prefix(while: { $0 != " " })
        return path.isEmpty ? nil : String(path)
    }
}

/// Parsed `launchctl print gui/<uid>/<label>`. The output is not a stable API, so every field is optional-ish.
public struct LaunchState: Equatable, Sendable {
    public var loaded: Bool
    public var running: Bool
    public var lastExit: Int?

    public static let notLoaded = LaunchState(loaded: false, running: false, lastExit: nil)

    /// `nil` or text without a service block means not loaded (launchctl exits non-zero).
    public static func parse(_ output: String?) -> LaunchState {
        guard let output, output.contains(" = {") else { return .notLoaded }
        var state = LaunchState(loaded: true, running: false, lastExit: nil)
        for raw in output.split(whereSeparator: \.isNewline) {
            let line = raw.trimmingCharacters(in: .whitespaces)
            guard let eq = line.range(of: " = ") else { continue }
            let key = line[..<eq.lowerBound]
            let value = line[eq.upperBound...].trimmingCharacters(in: .whitespaces)
            switch key {
            case "state": state.running = (value == "running")
            case "last exit code", "last exit status": state.lastExit = Int(value)
            default: break
            }
        }
        return state
    }
}

/// The two keys of `runway.json` the app cares about.
public struct RunwayConfig: Equatable, Sendable {
    public var tracker: String
    public var projectName: String?

    public static func parse(_ data: Data) -> RunwayConfig {
        var config = RunwayConfig(tracker: "markdown", projectName: nil)
        guard let json = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any] else { return config }
        if let tracker = json["tracker"] as? String { config.tracker = tracker }
        if let linear = json["linear"] as? [String: Any] { config.projectName = linear["project"] as? String }
        return config
    }
}

/// One Runway loop as the views see it.
public struct Project: Identifiable, Equatable, Sendable {
    public var id: String { label }
    public let label: String
    public let name: String
    public let repoPath: String?
    public let tracker: String?
    public let interval: Int?
    public let logPath: String?
    public let loaded: Bool
    public let running: Bool
    public let lastExit: Int?
    /// Set when the project can't be read (bad plist, missing repo). The row shows it instead of crashing.
    public let error: String?
}

public struct ProjectDiscovery {
    public static let labelPrefix = "com.joe.runway."

    public let launchAgentsDir: URL
    /// Returns `launchctl print` output for a label, or nil if it exited non-zero.
    public let launchctlPrint: (String) -> String?

    public init(launchAgentsDir: URL = ProjectDiscovery.defaultLaunchAgentsDir,
                launchctlPrint: @escaping (String) -> String? = ProjectDiscovery.systemLaunchctlPrint) {
        self.launchAgentsDir = launchAgentsDir
        self.launchctlPrint = launchctlPrint
    }

    public static var defaultLaunchAgentsDir: URL {
        FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/LaunchAgents")
    }

    public static let systemLaunchctlPrint: (String) -> String? = { label in
        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/bin/launchctl")
        process.arguments = ["print", "gui/\(getuid())/\(label)"]
        let pipe = Pipe()
        process.standardOutput = pipe
        process.standardError = Pipe()
        do { try process.run() } catch { return nil }
        let data = pipe.fileHandleForReading.readDataToEndOfFile()
        process.waitUntilExit()
        guard process.terminationStatus == 0 else { return nil }
        return String(decoding: data, as: UTF8.self)
    }

    public func discover() -> [Project] {
        let files = (try? FileManager.default.contentsOfDirectory(at: launchAgentsDir, includingPropertiesForKeys: nil)) ?? []
        return files
            .filter { $0.pathExtension == "plist" && $0.lastPathComponent.hasPrefix(Self.labelPrefix) }
            .sorted { $0.lastPathComponent < $1.lastPathComponent }
            .map(project(at:))
    }

    private func project(at plist: URL) -> Project {
        let fileLabel = plist.deletingPathExtension().lastPathComponent
        let fallbackName = String(fileLabel.dropFirst(Self.labelPrefix.count))

        let job: LaunchJob
        do {
            job = try LaunchJob.parse(plist: try Data(contentsOf: plist))
        } catch {
            return Project(label: fileLabel, name: fallbackName, repoPath: nil, tracker: nil, interval: nil,
                           logPath: nil, loaded: false, running: false, lastExit: nil,
                           error: "Can't read \(plist.lastPathComponent)")
        }

        let state = LaunchState.parse(launchctlPrint(job.label))
        let repoName = URL(fileURLWithPath: job.repoPath).lastPathComponent

        var isDir: ObjCBool = false
        guard FileManager.default.fileExists(atPath: job.repoPath, isDirectory: &isDir), isDir.boolValue else {
            return Project(label: job.label, name: repoName, repoPath: job.repoPath, tracker: nil,
                           interval: job.interval, logPath: job.logPath, loaded: state.loaded,
                           running: state.running, lastExit: state.lastExit,
                           error: "Repo not found: \(job.repoPath)")
        }

        let configURL = URL(fileURLWithPath: job.repoPath).appendingPathComponent("runway.json")
        let config = (try? Data(contentsOf: configURL)).map(RunwayConfig.parse)
        return Project(label: job.label, name: config?.projectName ?? repoName, repoPath: job.repoPath,
                       tracker: config?.tracker, interval: job.interval, logPath: job.logPath,
                       loaded: state.loaded, running: state.running, lastExit: state.lastExit,
                       error: nil)
    }
}
