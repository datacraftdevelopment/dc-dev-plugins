import Foundation

// "Update Runway" (docs/specs/app-updates.md, "Bring the rest along" and "Parity you can see"): the commands it runs,
// the decisions between them, the version-change trigger and the Behind badge. The views only display these.
// It never stashes, resets, switches branches or touches launchctl, and git only ever runs in the engine checkout.

// MARK: commands

/// Every command "Update Runway" and the parity line run, all against the engine checkout.
public struct UpdateCommands: Equatable, Sendable {
    public let checkout: String

    public init(checkout: String) { self.checkout = checkout }

    private func git(_ args: String...) -> Command {
        Command(executable: "/usr/bin/env", arguments: ["git", "-C", checkout] + args)
    }

    public var branch: Command { git("rev-parse", "--abbrev-ref", "HEAD") }
    public var porcelain: Command { git("status", "--porcelain") }
    public var pull: Command { git("pull", "--ff-only", "origin", "main") }
    public var shortSHA: Command { git("rev-parse", "--short", "HEAD") }
    public var fetch: Command { git("fetch", "origin", "main") }
    public var commitsBehind: Command { git("rev-list", "--count", "HEAD..origin/main") }
    /// Through a login shell, the same way the setup checks run `claude`, so PATH matches.
    public var marketplaceUpdate: Command { SetupChecks.probe("claude plugin marketplace update dc-dev-plugins") }
    public var pluginUpdate: Command { SetupChecks.probe("claude plugin update pm@dc-dev-plugins") }

    public var all: [Command] {
        [branch, porcelain, pull, shortSHA, fetch, commitsBehind, marketplaceUpdate, pluginUpdate]
    }

    /// The engine checkout's `pm/.claude-plugin/plugin.json`, whose version the installed pm is compared with.
    public var pmManifest: URL {
        URL(fileURLWithPath: checkout).appendingPathComponent("pm/.claude-plugin/plugin.json")
    }
}

// MARK: decisions

/// Whether the engine checkout may be pulled: only on a clean `main`.
public enum CheckoutGate: Equatable, Sendable {
    case pull
    case skip(String)

    public static func decide(branch: String, porcelain: String) -> CheckoutGate {
        if branch.trimmingCharacters(in: .whitespacesAndNewlines) != "main" { return .skip("checkout is on a branch") }
        if !porcelain.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty { return .skip("uncommitted changes") }
        return .pull
    }
}

public enum UpdateOutcome: Equatable, Sendable {
    /// A loop is mid-tick; try again on the next status refresh.
    case waiting
    case failed(step: String, output: String)
    case done(String)

    public var summary: String {
        switch self {
        case .waiting: return "Waiting for a loop to finish its tick…"
        case .failed(let step, let output): return output.isEmpty ? "\(step) failed" : "\(step) failed:\n\(output)"
        case .done(let message): return message
        }
    }
}

public enum RunwayUpdate {
    /// A heartbeat in an active phase whose process is alive. A dead tick doesn't count, or the update would wait forever.
    public static func midTick(_ heartbeats: [Heartbeat?], pidAlive: (Int) -> Bool) -> Bool {
        heartbeats.contains { $0?.isLive(pidAlive: pidAlive) == true }
    }

    /// The spec's steps in order, stopping at the first failure with that step's output.
    public static func run(commands: UpdateCommands, midTick: Bool, installedPm: () -> String?,
                           run: (Command) async -> CommandResult) async -> UpdateOutcome {
        if midTick { return .waiting }
        let branch = await run(commands.branch)
        let porcelain = await run(commands.porcelain)
        var note = ""
        let gate: CheckoutGate = branch.succeeded && porcelain.succeeded
            ? CheckoutGate.decide(branch: branch.stdout, porcelain: porcelain.stdout)
            : .skip("can't read the checkout's git state")
        switch gate {
        case .skip(let why): note = "Engine pull skipped: \(why). "
        case .pull:
            let result = await run(commands.pull)
            if !result.succeeded { return failed("git pull --ff-only origin main", result) }
        }
        for (step, command) in [("claude plugin marketplace update dc-dev-plugins", commands.marketplaceUpdate),
                                ("claude plugin update pm@dc-dev-plugins", commands.pluginUpdate)] {
            let result = await run(command)
            if !result.succeeded { return failed(step, result) }
        }
        let sha = await run(commands.shortSHA)
        let engine = sha.succeeded && !sha.stdout.isEmpty ? sha.stdout : "?"
        return .done(note + "Updated: engine \(engine), pm \(installedPm() ?? "?"). "
                     + "Restart open Claude sessions to pick up the new skills.")
    }

    private static func failed(_ step: String, _ result: CommandResult) -> UpdateOutcome {
        let output = [result.stdout, result.stderr].filter { !$0.isEmpty }.joined(separator: "\n")
        return .failed(step: step, output: output.isEmpty ? "exited with status \(result.status)" : output)
    }
}

/// Runs "Update Runway" once on the first launch after the bundle version changes.
public struct LaunchTrigger {
    public static let key = "lastLaunchedBuild"
    private let defaults: UserDefaults

    public init(defaults: UserDefaults = .standard) { self.defaults = defaults }

    /// True when `build` (`CFBundleVersion`) is newer than the one recorded. A build with no number (`swift run`) never is.
    public func isDue(build: String?) -> Bool {
        guard let build, let number = Int(build) else { return false }
        guard let recorded = defaults.string(forKey: Self.key).flatMap(Int.init) else { return true }
        return number > recorded
    }

    public func record(build: String?) {
        guard let build, Int(build) != nil else { return }
        defaults.set(build, forKey: Self.key)
    }
}

// MARK: parity

public enum DottedVersion {
    /// Numeric, part by part; a missing part counts as 0 ("1.0" equals "1.0.0").
    public static func isOlder(_ a: String, than b: String) -> Bool {
        let x = parts(a), y = parts(b)
        for i in 0..<max(x.count, y.count) {
            let l = i < x.count ? x[i] : 0, r = i < y.count ? y[i] : 0
            if l != r { return l < r }
        }
        return false
    }

    private static func parts(_ v: String) -> [Int] {
        v.trimmingCharacters(in: .whitespacesAndNewlines).split(separator: ".").map { Int($0.prefix { $0.isNumber }) ?? 0 }
    }
}

/// What this Mac runs, and what it's behind on. Unknown values (nil) never count as behind.
public struct Parity: Equatable, Sendable {
    public var app: String?
    public var feed: String?
    public var engineSHA: String?
    public var engineBranch: String?
    public var commitsBehind: Int?
    public var installedPm: String?
    public var checkoutPm: String?

    public init(app: String?, feed: String?, engineSHA: String?, engineBranch: String?, commitsBehind: Int?,
                installedPm: String?, checkoutPm: String?) {
        self.app = app
        self.feed = feed
        self.engineSHA = engineSHA
        self.engineBranch = engineBranch
        self.commitsBehind = commitsBehind
        self.installedPm = installedPm
        self.checkoutPm = checkoutPm
    }

    /// "Runway 0.1.0 · engine abc1234 (main) · pm 0.27.2"
    public var line: String {
        let engine = engineSHA.map { sha in engineBranch.map { "\(sha) (\($0))" } ?? sha } ?? "?"
        return "Runway \(app ?? "dev") · engine \(engine) · pm \(installedPm ?? "?")"
    }

    /// Each reason for the Behind badge; empty when up to date.
    public var behind: [String] {
        var reasons: [String] = []
        if let app, let feed, DottedVersion.isOlder(app, than: feed) { reasons.append("app \(app), latest \(feed)") }
        if let commitsBehind, commitsBehind > 0 {
            reasons.append("engine \(commitsBehind) commit\(commitsBehind == 1 ? "" : "s") behind origin/main")
        }
        if let installedPm, let checkoutPm, DottedVersion.isOlder(installedPm, than: checkoutPm) {
            reasons.append("pm \(installedPm), checkout has \(checkoutPm)")
        }
        return reasons
    }
}

/// The `git fetch` (and the feed read) behind the Behind badge run at most hourly.
public enum FetchThrottle {
    public static let interval: TimeInterval = 3600

    public static func isDue(last: Date?, now: Date = Date()) -> Bool {
        guard let last else { return true }
        return now.timeIntervalSince(last) >= interval
    }
}

public enum PluginVersions {
    public static let registryURL = FileManager.default.homeDirectoryForCurrentUser
        .appendingPathComponent(".claude/plugins/installed_plugins.json")

    /// The user-scope install of `pm@dc-dev-plugins` in Claude Code's plugin registry.
    public static func installedPm(registry: Data) -> String? {
        guard let json = (try? JSONSerialization.jsonObject(with: registry)) as? [String: Any],
              let plugins = json["plugins"] as? [String: Any] else { return nil }
        let entry = plugins["pm@dc-dev-plugins"]
        let installs = (entry as? [[String: Any]]) ?? (entry as? [String: Any]).map { [$0] } ?? []
        let user = installs.first { ($0["scope"] as? String) == "user" } ?? installs.first
        return user?["version"] as? String
    }

    public static func installedPm(url: URL = registryURL) -> String? {
        (try? Data(contentsOf: url)).flatMap { installedPm(registry: $0) }
    }

    /// `version` from a `plugin.json`.
    public static func manifestVersion(_ data: Data) -> String? {
        ((try? JSONSerialization.jsonObject(with: data)) as? [String: Any])?["version"] as? String
    }
}

/// The release feed's latest version: the first item's `sparkle:shortVersionString`.
public enum Appcast {
    public static let feedURL = URL(string: "https://github.com/datacraftdevelopment/dc-dev-plugins/releases/latest/download/appcast.xml")!

    public static func latestVersion(_ data: Data) -> String? {
        let text = String(decoding: data, as: UTF8.self)
        guard let open = text.range(of: "<sparkle:shortVersionString>"),
              let close = text.range(of: "</sparkle:shortVersionString>", range: open.upperBound..<text.endIndex) else { return nil }
        let version = text[open.upperBound..<close.lowerBound].trimmingCharacters(in: .whitespacesAndNewlines)
        return version.isEmpty ? nil : version
    }
}
