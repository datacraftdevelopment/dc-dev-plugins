import Foundation

// The "Set up a loop" sheet's logic: what to check on this Mac, the steps to run, and how to run them.
// Steps are data (`SetupStep`), so a later step (installing Ringer) is one more entry in `SetupPlan.steps`.

// MARK: checks

public struct SetupCheck: Equatable, Sendable, Identifiable {
    public enum Status: Equatable, Sendable { case ok, missing }
    /// What the sheet can offer to do about a check.
    public enum Fix: Equatable, Sendable { case cloneEngine, signIn, saveKey, ghLogin }

    public let id: String
    public let title: String
    public let status: Status
    public let detail: String
    public let required: Bool
    public let fix: Fix?

    public init(id: String, title: String, status: Status, detail: String, required: Bool, fix: Fix? = nil) {
        self.id = id
        self.title = title
        self.status = status
        self.detail = detail
        self.required = required
        self.fix = fix
    }
}

public enum SetupChecks {
    public static let engineURL = "https://github.com/datacraftdevelopment/dc-dev-plugins.git"
    public static let keychainService = "runway-linear"

    /// Runs a command line in a login shell, so the user's PATH (npm globals, ~/.local/bin) applies as it does for the loop.
    public static func probe(_ line: String) -> Command {
        Command(executable: "/bin/zsh", arguments: ["-lc", line])
    }

    public static func python(run: (Command) async -> CommandResult) async -> SetupCheck {
        let result = await run(probe("python3 --version"))
        let text = (result.stdout + " " + result.stderr).trimmingCharacters(in: .whitespacesAndNewlines)
        guard result.succeeded, let (major, minor) = pythonVersion(text) else {
            return SetupCheck(id: "python", title: "Python 3.9+", status: .missing,
                              detail: result.succeeded ? "Couldn't read the version" : "Not installed", required: true)
        }
        let enough = major > 3 || (major == 3 && minor >= 9)
        return SetupCheck(id: "python", title: "Python 3.9+", status: enough ? .ok : .missing,
                          detail: enough ? text : "\(text) is too old, need 3.9 or newer", required: true)
    }

    static func pythonVersion(_ text: String) -> (Int, Int)? {
        guard let match = text.range(of: #"Python (\d+)\.(\d+)"#, options: .regularExpression) else { return nil }
        let parts = text[match].dropFirst("Python ".count).split(separator: ".").compactMap { Int($0) }
        return parts.count >= 2 ? (parts[0], parts[1]) : nil
    }

    public static func git(run: (Command) async -> CommandResult) async -> SetupCheck {
        await tool(id: "git", title: "git", line: "git --version", required: true, run: run)
    }

    /// Installed is what `claude --version` proves. Sign-in can't be checked silently, so it always offers the Terminal.
    public static func claude(run: (Command) async -> CommandResult) async -> SetupCheck {
        await tool(id: "claude", title: "Claude Code", line: "claude --version", required: true, fixWhenOk: .signIn, run: run)
    }

    public static func codex(run: (Command) async -> CommandResult) async -> SetupCheck {
        await tool(id: "codex", title: "codex (optional)", line: "codex --version", required: false, run: run)
    }

    public static func cursorAgent(run: (Command) async -> CommandResult) async -> SetupCheck {
        await tool(id: "cursor-agent", title: "cursor-agent (optional)", line: "cursor-agent --version", required: false, run: run)
    }

    private static func tool(id: String, title: String, line: String, required: Bool, fixWhenOk: SetupCheck.Fix? = nil,
                             run: (Command) async -> CommandResult) async -> SetupCheck {
        let result = await run(probe(line))
        guard result.succeeded else {
            return SetupCheck(id: id, title: title, status: .missing, detail: "Not installed", required: required)
        }
        let version = result.stdout.split(whereSeparator: \.isNewline).first.map(String.init) ?? "installed"
        return SetupCheck(id: id, title: title, status: .ok, detail: version, required: required, fix: fixWhenOk)
    }

    /// The engine is a dc-dev-plugins checkout holding all three scripts.
    public static func engine(checkout: String?, fileExists: (String) -> Bool) -> SetupCheck {
        guard let checkout, !checkout.isEmpty else {
            return SetupCheck(id: "engine", title: "Runway engine", status: .missing,
                              detail: "No dc-dev-plugins checkout chosen", required: true, fix: .cloneEngine)
        }
        let tools = RunwayTools(checkout: checkout)
        let present = [tools.runwayScript, tools.scheduleScript, tools.setupScript].allSatisfy(fileExists)
        return present
            ? SetupCheck(id: "engine", title: "Runway engine", status: .ok, detail: checkout, required: true)
            : SetupCheck(id: "engine", title: "Runway engine", status: .missing,
                         detail: "Scripts not found under \(checkout)", required: true, fix: .cloneEngine)
    }

    public static func clonedCheckout(into folder: String) -> String {
        URL(fileURLWithPath: folder).appendingPathComponent("dc-dev-plugins").path
    }

    public static func cloneCommand(into folder: String) -> Command {
        Command(executable: "/usr/bin/env", arguments: ["git", "clone", engineURL, clonedCheckout(into: folder)])
    }

    /// Asks the keychain whether the item exists. No `-w` or `-g`, so the key itself is never printed.
    public static func linearKey(run: (Command) async -> CommandResult) async -> SetupCheck {
        let result = await run(Command(executable: "/usr/bin/security", arguments: ["find-generic-password", "-s", keychainService]))
        return result.succeeded
            ? SetupCheck(id: "linear-key", title: "Linear API key", status: .ok, detail: "In the keychain (\(keychainService))", required: true)
            : SetupCheck(id: "linear-key", title: "Linear API key", status: .missing,
                         detail: "No keychain item \(keychainService)", required: true, fix: .saveKey)
    }

    /// GitHub needs `gh` installed and signed in; `gh auth status` exits non-zero when it isn't.
    public static func githubAuth(run: (Command) async -> CommandResult) async -> SetupCheck {
        let result = await run(probe("gh auth status"))
        if result.succeeded {
            return SetupCheck(id: "gh-auth", title: "GitHub sign-in (gh)", status: .ok, detail: "Signed in", required: true)
        }
        let text = (result.stdout + " " + result.stderr).lowercased()
        if result.status == 127 || text.contains("command not found") {
            return SetupCheck(id: "gh-auth", title: "GitHub sign-in (gh)", status: .missing,
                              detail: "gh is not installed (brew install gh)", required: true)
        }
        return SetupCheck(id: "gh-auth", title: "GitHub sign-in (gh)", status: .missing,
                          detail: "Not signed in to GitHub", required: true, fix: .ghLogin)
    }

    /// Opens Terminal running `gh auth login`, which walks through the sign-in.
    public static let ghLoginCommand = Command(executable: "/usr/bin/osascript", arguments: [
        "-e", "tell application \"Terminal\" to activate",
        "-e", "tell application \"Terminal\" to do script \"gh auth login\""])

    public static func all(tracker: SetupTracker, checkout: String?, fileExists: (String) -> Bool,
                           run: (Command) async -> CommandResult) async -> [SetupCheck] {
        var checks = [await python(run: run), await git(run: run), await claude(run: run),
                      await codex(run: run), await cursorAgent(run: run),
                      engine(checkout: checkout, fileExists: fileExists)]
        if tracker == .linear { checks.append(await linearKey(run: run)) }
        if tracker == .github { checks.append(await githubAuth(run: run)) }
        return checks
    }

    /// The required checks that aren't met; the sheet won't run while any remain.
    public static func blocking(_ checks: [SetupCheck]) -> [SetupCheck] {
        checks.filter { $0.required && $0.status != .ok }
    }
}

// MARK: the Linear key

public enum Redactor {
    public static func scrub(_ text: String, secret: String) -> String {
        secret.isEmpty ? text : text.replacingOccurrences(of: secret, with: "••••")
    }
}

/// Saves the key with `security add-generic-password`. It goes to the keychain only: never a file, never a log, and
/// never into the text shown or the output returned. (`security` takes the value as an argument; there is no stdin form.)
public enum LinearKey {
    public static func save(_ key: String, account: String = NSUserName(),
                            run: (Command) async -> CommandResult) async -> CommandResult {
        let secret = key.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !secret.isEmpty else { return CommandResult(status: 1, stdout: "", stderr: "Paste the Linear key first.") }
        let result = await run(Command(executable: "/usr/bin/security", arguments: [
            "add-generic-password", "-U", "-s", SetupChecks.keychainService, "-a", account, "-w", secret]))
        return CommandResult(status: result.status, stdout: Redactor.scrub(result.stdout, secret: secret),
                             stderr: Redactor.scrub(result.stderr, secret: secret))
    }

    /// What the sheet shows for this step, with the key masked.
    public static func displayText(account: String = NSUserName()) -> String {
        "security add-generic-password -U -s \(SetupChecks.keychainService) -a \(account) -w ••••"
    }
}

// MARK: the plan

public enum SetupTracker: String, CaseIterable, Equatable, Sendable { case linear, github, git }

public struct SetupConfig: Equatable, Sendable {
    public var repo: String
    public var tracker: SetupTracker
    public var team: String
    public var project: String
    public var harness: String
    public var minutes: Int
    /// `owner/name` for the GitHub tracker; empty lets setup.sh read it from the clone's origin.
    public var githubRepo: String

    public init(repo: String, tracker: SetupTracker, team: String, project: String, harness: String, minutes: Int,
                githubRepo: String = "") {
        self.repo = repo
        self.tracker = tracker
        self.team = team
        self.project = project
        self.harness = harness
        self.minutes = minutes
        self.githubRepo = githubRepo
    }
}

public struct SetupStep: Equatable, Sendable, Identifiable {
    public enum Action: Equatable, Sendable {
        case run(Command)
        /// Runs a command whose JSON output is read for other machines' claims, not shown. Never fails the flow.
        case claimCheck(Command)
        case setHarness(repo: String, name: String)
    }

    public let id: String
    public let title: String
    public let action: Action

    public init(id: String, title: String, action: Action) {
        self.id = id
        self.title = title
        self.action = action
    }

    /// The command as the sheet shows it before running it.
    public var display: String {
        switch action {
        case .run(let command), .claimCheck(let command):
            let words = command.executable == "/usr/bin/env"
                ? command.arguments
                : [URL(fileURLWithPath: command.executable).lastPathComponent] + command.arguments
            return words.map(Self.quote).joined(separator: " ")
        case .setHarness(let repo, let name):
            return "set \"harness\": \"\(name)\" in \(repo)/runway.json"
        }
    }

    static func quote(_ word: String) -> String {
        if !word.isEmpty, word.range(of: #"^[A-Za-z0-9_./:=@%+,-]+$"#, options: .regularExpression) != nil { return word }
        return "'" + word.replacingOccurrences(of: "'", with: "'\\''") + "'"
    }
}

public enum SetupPlan {
    public static func problems(_ config: SetupConfig) -> [String] {
        var found: [String] = []
        if config.repo.trimmingCharacters(in: .whitespaces).isEmpty { found.append("Choose the repo folder.") }
        if config.tracker == .linear {
            if config.team.trimmingCharacters(in: .whitespaces).isEmpty { found.append("Enter the Linear team key.") }
            if config.project.trimmingCharacters(in: .whitespaces).isEmpty { found.append("Enter the Linear project name.") }
        }
        let githubRepo = config.githubRepo.trimmingCharacters(in: .whitespaces)
        if config.tracker == .github, !githubRepo.isEmpty,
           githubRepo.range(of: #"^[^/\s]+/[^/\s]+$"#, options: .regularExpression) == nil {
            found.append("The GitHub repo must look like owner/name.")
        }
        if config.minutes < 1 { found.append("The interval must be at least 1 minute.") }
        return found
    }

    /// The commands the sheet shows and then runs, in order. Add a step here to extend the flow.
    public static func steps(_ config: SetupConfig, tools: RunwayTools) -> [SetupStep] {
        let python = { (args: [String]) in Command(executable: "/usr/bin/env", arguments: ["python3", tools.runwayScript, "--root", config.repo] + args) }
        var steps: [SetupStep] = []
        if config.tracker == .linear || config.tracker == .github {
            if config.tracker == .linear {
                steps.append(SetupStep(id: "setup-repo", title: "Point the repo at Linear", action: .run(
                    Command(executable: "/bin/bash", arguments: [tools.setupScript, config.repo, config.team, config.project]))))
            } else {
                let githubRepo = config.githubRepo.trimmingCharacters(in: .whitespaces)
                steps.append(SetupStep(id: "setup-repo", title: "Point the repo at GitHub", action: .run(
                    Command(executable: "/bin/bash", arguments: [tools.setupScript, config.repo, "--github"]
                            + (githubRepo.isEmpty ? [] : [githubRepo])))))
            }
            if config.harness != "claude" {
                steps.append(SetupStep(id: "harness", title: "Set the harness", action: .setHarness(repo: config.repo, name: config.harness)))
            }
            steps.append(SetupStep(id: "runway-setup",
                                   title: config.tracker == .github ? "Check gh and create the labels" : "Check the key, team and project",
                                   action: .run(python(["setup"]))))
            steps.append(SetupStep(id: "claims", title: "Look for tickets claimed by another Mac", action: .claimCheck(python(["status", "--json"]))))
        } else if config.harness != "claude" {
            steps.append(SetupStep(id: "harness", title: "Set the harness", action: .setHarness(repo: config.repo, name: config.harness)))
        }
        steps.append(SetupStep(id: "install", title: "Install the schedule", action: .run(tools.start(repo: config.repo, minutes: config.minutes))))
        return steps
    }
}

extension RunwayTools {
    /// `setup.sh`, next to `schedule.sh`; in the old `experiments/03-linear/` layout it sat under `practice/`.
    public var setupScript: String {
        let dir = URL(fileURLWithPath: scheduleScript).deletingLastPathComponent()
        return dir.appendingPathComponent(dir.lastPathComponent == "03-linear" ? "practice/setup.sh" : "setup.sh").path
    }
}

// MARK: claims

/// A ticket another machine holds the claim on (DAT-11's stamp), found in `runway status --json`.
public struct ForeignClaim: Equatable, Sendable {
    public let ticket: String
    public let title: String
    public let machine: String

    public init(ticket: String, title: String, machine: String) {
        self.ticket = ticket
        self.title = title
        self.machine = machine
    }

    public static func parse(_ data: Data) -> [ForeignClaim]? {
        guard let json = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any] else { return nil }
        let me = json["machine"] as? String
        return ((json["tickets"] as? [[String: Any]]) ?? []).compactMap { entry in
            guard entry["status"] as? String == "claimed", let id = entry["id"] as? String,
                  let machine = entry["claimed_by"] as? String, !machine.isEmpty, machine != me else { return nil }
            return ForeignClaim(ticket: id, title: (entry["title"] as? String) ?? "", machine: machine)
        }
    }
}

// MARK: harness

public enum HarnessEdit {
    struct Failure: LocalizedError {
        let errorDescription: String?
    }

    /// Sets `"harness"` in the repo's runway.json. A name other than claude needs a `harnesses` profile, or the
    /// engine would quietly fall back to claude, so that refuses without touching the file.
    public static func set(_ name: String, inRepo repo: String) throws {
        let url = URL(fileURLWithPath: repo).appendingPathComponent("runway.json")
        guard let data = try? Data(contentsOf: url),
              var json = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any] else {
            throw Failure(errorDescription: "Can't read \(url.path).")
        }
        let profiles = json["harnesses"] as? [String: Any] ?? [:]
        if name != "claude", profiles[name] == nil {
            throw Failure(errorDescription: "runway.json has no harnesses.\(name) profile, so Runway would fall back to claude. Add one, then run again.")
        }
        if (json["harness"] as? String ?? "claude") == name { return }
        json["harness"] = name
        try JSONSerialization.data(withJSONObject: json, options: [.prettyPrinted, .sortedKeys]).write(to: url, options: .atomic)
    }
}

// MARK: running

public enum SetupOutcome: Equatable, Sendable {
    case completed(warnings: [ForeignClaim])
    /// The step that failed and everything it printed.
    case failed(SetupStep, output: String)
}

public enum SetupRunner {
    /// Runs the steps in order and stops at the first failure. Every step is safe to repeat (setup.sh keeps an existing
    /// runway.json, `runway setup` only creates missing labels, `schedule.sh install` replaces the job), so a re-run starts from the top.
    public static func run(_ steps: [SetupStep],
                           execute: @Sendable (Command, @escaping @Sendable (String) -> Void) async -> CommandResult,
                           setHarness: (String, String) throws -> Void = { try HarnessEdit.set($1, inRepo: $0) },
                           started: (SetupStep) -> Void = { _ in },
                           output: @escaping @Sendable (String) -> Void = { _ in }) async -> SetupOutcome {
        var warnings: [ForeignClaim] = []
        for step in steps {
            started(step)
            output("$ " + step.display)
            switch step.action {
            case .setHarness(let repo, let name):
                do { try setHarness(repo, name) } catch {
                    let message = error.localizedDescription
                    output(message)
                    return .failed(step, output: message)
                }
            case .claimCheck(let command):
                let result = await execute(command) { _ in }
                if result.succeeded, let claims = ForeignClaim.parse(Data(result.stdout.utf8)) {
                    warnings = claims
                    output(claims.isEmpty ? "No tickets claimed by another Mac."
                                          : "\(claims.count) ticket\(claims.count == 1 ? "" : "s") claimed by another Mac.")
                } else {
                    output("couldn't check claims: \(result.failureMessage)")
                }
            case .run(let command):
                let lines = LineBox()
                let result = await execute(command) { line in lines.add(line); output(line) }
                if !result.succeeded {
                    for text in [result.stdout, result.stderr] where !text.isEmpty && !lines.joined.contains(text) {
                        lines.add(text)
                        output(text)
                    }
                    if lines.isEmpty { lines.add(result.failureMessage); output(result.failureMessage) }
                    return .failed(step, output: lines.joined)
                }
            }
        }
        return .completed(warnings: warnings)
    }

    private final class LineBox: @unchecked Sendable {
        private let lock = NSLock()
        private var lines: [String] = []
        func add(_ line: String) { lock.lock(); lines.append(line); lock.unlock() }
        var joined: String { lock.lock(); defer { lock.unlock() }; return lines.joined(separator: "\n") }
        var isEmpty: Bool { lock.lock(); defer { lock.unlock() }; return lines.isEmpty }
    }
}

extension SetupChecks {
    /// Opens Terminal running `claude`, which asks to sign in on first run.
    public static let signInCommand = Command(executable: "/usr/bin/osascript", arguments: [
        "-e", "tell application \"Terminal\" to activate",
        "-e", "tell application \"Terminal\" to do script \"claude\""])

    /// The checkout a `runway.py` path belongs to: `<checkout>/factory/plugin/runway/runway.py` (or the old `…/factory/experiments/01-runway/runway.py`).
    public static func checkout(ofRunwayScript path: String) -> String {
        var url = URL(fileURLWithPath: path)
        for _ in 0..<4 { url.deleteLastPathComponent() }
        return url.path
    }
}

// MARK: streaming

extension CommandRunner {
    /// Like `run`, but hands each line of output (stdout and stderr merged) to `onLine` as it arrives.
    /// The result carries all of it in `stdout`.
    public static func stream(_ command: Command, onLine: @escaping @Sendable (String) -> Void) async -> CommandResult {
        await withCheckedContinuation { continuation in
            DispatchQueue.global().async { continuation.resume(returning: streamSync(command, onLine)) }
        }
    }

    static func streamSync(_ command: Command, _ onLine: @Sendable (String) -> Void) -> CommandResult {
        let process = Process()
        process.executableURL = URL(fileURLWithPath: command.executable)
        process.arguments = command.arguments
        let pipe = Pipe()
        process.standardOutput = pipe
        process.standardError = pipe
        process.standardInput = FileHandle.nullDevice
        do { try process.run() } catch {
            return CommandResult(status: -1, stdout: "", stderr: error.localizedDescription)
        }
        var all = Data()
        var pending = Data()
        let newline = UInt8(ascii: "\n")
        while true {
            let chunk = pipe.fileHandleForReading.availableData
            if chunk.isEmpty { break }
            all.append(chunk)
            pending.append(chunk)
            while let index = pending.firstIndex(of: newline) {
                onLine(String(decoding: pending[pending.startIndex..<index], as: UTF8.self))
                pending = Data(pending[pending.index(after: index)...])
            }
        }
        if !pending.isEmpty { onLine(String(decoding: pending, as: UTF8.self)) }
        process.waitUntilExit()
        let text = String(decoding: all, as: UTF8.self).trimmingCharacters(in: .whitespacesAndNewlines)
        return CommandResult(status: process.terminationStatus, stdout: text, stderr: "")
    }
}
