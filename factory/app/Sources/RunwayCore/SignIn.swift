import Foundation

/// One sign-in check from `status --json`'s `signin.checks` (the engine's `_pm/runway-signin.json`).
public struct SignInCheck: Equatable, Sendable {
    public let name: String
    public let label: String
    /// The command line that fixes it (`claude auth login`), or nil when the engine has none.
    public let fix: String?
    public let ok: Bool
    public let detail: String

    public init(name: String, label: String, fix: String?, ok: Bool, detail: String) {
        self.name = name
        self.label = label
        self.fix = fix
        self.ok = ok
        self.detail = detail
    }

    /// The `checks` list of a `signin` object; nil or anything malformed reads as no checks.
    public static func parse(_ signin: Any?) -> [SignInCheck] {
        guard let checks = (signin as? [String: Any])?["checks"] as? [[String: Any]] else { return [] }
        return checks.compactMap { c in
            guard let name = c["name"] as? String, !name.isEmpty else { return nil }
            let fix = (c["fix"] as? String).flatMap { $0.isEmpty ? nil : $0 }
            return SignInCheck(name: name, label: (c["label"] as? String) ?? name.capitalized, fix: fix,
                               ok: (c["ok"] as? Bool) == true, detail: (c["detail"] as? String) ?? "")
        }
    }
}

/// A tool this Mac needs signed in again, as the top of "Needs you" shows it, with the button's command.
public struct SignInNeed: Equatable, Sendable, Identifiable {
    /// The check's name (`claude`, `gh`, `codex`, `linear`).
    public let id: String
    public let label: String
    public let fix: String?
    public let detail: String

    public init(id: String, label: String, fix: String?, detail: String) {
        self.id = id
        self.label = label
        self.fix = fix
        self.detail = detail
    }

    /// The pause reason the engine writes when an agent call failed on auth (pause_for_auth).
    public static let signedOutReason = "signed-out"
    /// Used only when the engine's own checks didn't name Claude's fix.
    static let claudeFix = "claude auth login"

    /// Every failing check across the projects (a sign-in is per Mac, so one row per tool), and Claude Code
    /// when the machine-wide pause says an agent call failed on auth. A pause Joe set himself adds nothing.
    public static func resolve(_ snapshots: [StatusSnapshot], pause: PauseInfo?) -> [SignInNeed] {
        var needs: [SignInNeed] = []
        for check in snapshots.flatMap(\.signin) where !check.ok && !needs.contains(where: { $0.id == check.name }) {
            needs.append(SignInNeed(id: check.name, label: check.label, fix: check.fix, detail: check.detail))
        }
        if pause?.reason == signedOutReason, !needs.contains(where: { $0.id == "claude" }) {
            let known = snapshots.flatMap(\.signin).first { $0.name == "claude" }
            needs.insert(SignInNeed(id: "claude", label: known?.label ?? "Claude Code", fix: known?.fix ?? claudeFix,
                                    detail: "Runway paused: an agent call failed on sign-in"), at: 0)
        }
        return needs
    }

    /// What the pane runs: the fix through a login shell, so PATH matches what the loop sees.
    public func session(home: String = NSHomeDirectory()) -> LaunchSpec? {
        fix.map { LaunchSpec(executable: "/bin/zsh", arguments: ["-lc", $0], workingDirectory: home) }
    }

    /// The registry key for this need's pane tab, so a second click selects the running one.
    public var sessionKey: String { "signin:\(id)" }
}

/// What to run after a sign-in session ends, given each project's `runway signin` exit.
public enum SignInFollowUp {
    /// When every project's checks passed: lift a pause the engine set for sign-in (a hand-set one stays),
    /// then run a tick now for each loop that was waiting on a sign-in. Nothing when any check still fails.
    public static func commands(allPassed: Bool, tools: RunwayTools, waitingLoops: [String]) -> [Command] {
        guard allPassed else { return [] }
        return [tools.resumeIfSignedOut()] + waitingLoops.map { RunwayTools.runNow(label: $0) }
    }

    /// A loaded loop whose last tick waited or paused (sign-in failures write heartbeat `waiting`, pause_for_auth `paused`).
    public static func wasWaiting(_ heartbeat: Heartbeat?) -> Bool {
        guard let heartbeat else { return false }
        return heartbeat.phase == "paused" || (heartbeat.phase == "waiting" && heartbeat.reason?.contains("sign") == true)
    }

    /// The line the window shows once the re-check is done.
    public static func note(label: String, failing: [SignInCheck]) -> String {
        failing.isEmpty ? "\(label): signed in. Runway carries on." : failing.map(\.detail).joined(separator: "; ")
    }
}

extension RunwayTools {
    /// `runway --root <repo> signin --json`: the checks the next tick would run, recorded for status. Exit 0 when all pass.
    public func signin(repo: String) -> Command {
        Command(executable: "/usr/bin/env", arguments: ["python3", runwayScript, "--root", repo, "signin", "--json"])
    }

    /// `runway resume --if-reason signed-out`: lifts the pause only when sign-in set it.
    public func resumeIfSignedOut() -> Command {
        Command(executable: "/usr/bin/env",
                arguments: ["python3", runwayScript, "resume", "--if-reason", SignInNeed.signedOutReason])
    }
}
