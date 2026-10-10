import Foundation

/// The kinds `runway status --json` puts in a ticket's `errored` field, in the words the flag shows.
public enum ErroredKind {
    static let words: [String: String] = [
        "check-failed": "check failed", "merge-conflict": "merge conflict", "agent-failed": "agent failed",
        "no-commits": "no commits", "signed-out": "signed out",
    ]

    /// "check failed" for `check-failed`; a kind this app doesn't know yet keeps its own name, dashes as spaces.
    public static func words(_ kind: String) -> String {
        words[kind] ?? kind.replacingOccurrences(of: "-", with: " ")
    }
}

extension StatusSnapshot {
    /// `runway discuss` takes a waiting ticket or an errored one; the button shows for those and no others.
    public func canTalkThrough(_ ticket: String) -> Bool {
        errored[ticket] != nil || tickets.contains { $0.id == ticket }
    }
}

/// The Terminal commands behind the "Talk it through" button. The engine owns the brief and the prompt;
/// the app only opens Terminal in the repo running `runway discuss`.
extension RunwayTools {
    public func discuss(ticket: String, repo: String) -> Command {
        terminal(repo: repo, discussTail(ticket: ticket))
    }

    public func discussLoop(repo: String) -> Command {
        terminal(repo: repo, "discuss --loop")
    }

    /// The one shell line both launchers run: Terminal's `do script` and the window's pane.
    func shellLine(repo: String, _ tail: String) -> String {
        "cd \(Self.shellQuote(repo)) && python3 \(Self.shellQuote(runwayScript)) \(tail)"
    }

    private func terminal(repo: String, _ tail: String) -> Command {
        let shell = shellLine(repo: repo, tail)
        let literal = shell.replacingOccurrences(of: "\\", with: "\\\\").replacingOccurrences(of: "\"", with: "\\\"")
        return Command(executable: "/usr/bin/osascript", arguments: [
            "-e", "tell application \"Terminal\" to activate",
            "-e", "tell application \"Terminal\" to do script \"\(literal)\""])
    }

    func discussTail(ticket: String) -> String { "discuss " + Self.shellQuote(ticket) }

    /// Always single-quoted, so a space, a quote or a `$` in a path stays one word.
    static func shellQuote(_ word: String) -> String {
        "'" + word.replacingOccurrences(of: "'", with: "'\\''") + "'"
    }
}
