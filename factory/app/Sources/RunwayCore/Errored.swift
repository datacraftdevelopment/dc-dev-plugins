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

    /// A Finished row that ended "needs you" offers the button only while its ticket still waits on Joe.
    /// An errored flag alone doesn't count here: it stays until the next merge, so after a `go` it would keep
    /// the button on a ticket that has been answered.
    public func canTalkThrough(finished: FinishedTicket) -> Bool {
        finished.result == "needs-human" && tickets.contains { $0.id == finished.ticket }
    }

    /// "Resume worker" shows only when the engine says the ticket's latest attempt is a claude session it can reopen.
    public func canResumeWorker(_ ticket: String) -> Bool { resumable.contains(ticket) }
}

/// The Terminal commands behind the "Talk it through" button. The engine owns the brief and the prompt;
/// the app only opens Terminal in the repo running `runway discuss`.
extension RunwayTools {
    public func discuss(ticket: String, repo: String) -> Command {
        terminal(repo: repo, discussTail(ticket: ticket))
    }

    /// `runway discuss <ticket> --resume`: the worker's own conversation, in Terminal.
    public func discussResume(ticket: String, repo: String) -> Command {
        terminal(repo: repo, discussTail(ticket: ticket, resume: true))
    }

    public func discussLoop(repo: String) -> Command {
        terminal(repo: repo, "discuss --loop")
    }

    /// `runway discuss --review`: the last finish review's own conversation, in Terminal.
    public func discussReview(repo: String) -> Command {
        terminal(repo: repo, "discuss --review")
    }

    /// The one shell line both launchers run: Terminal's `do script` and the window's pane.
    func shellLine(repo: String, _ tail: String) -> String {
        "cd \(Self.shellQuote(repo)) && python3 \(Self.shellQuote(runwayScript)) \(tail)"
    }

    private func terminal(repo: String, _ tail: String) -> Command {
        Self.terminal(line: shellLine(repo: repo, tail))
    }

    /// Terminal.app running one shell line (what "Pop out to Terminal" does for any pane session).
    public static func terminal(line: String) -> Command {
        let literal = line.replacingOccurrences(of: "\\", with: "\\\\").replacingOccurrences(of: "\"", with: "\\\"")
        return Command(executable: "/usr/bin/osascript", arguments: [
            "-e", "tell application \"Terminal\" to activate",
            "-e", "tell application \"Terminal\" to do script \"\(literal)\""])
    }

    func discussTail(ticket: String, resume: Bool = false) -> String {
        "discuss " + Self.shellQuote(ticket) + (resume ? " --resume" : "")
    }

    /// Always single-quoted, so a space, a quote or a `$` in a path stays one word.
    static func shellQuote(_ word: String) -> String {
        "'" + word.replacingOccurrences(of: "'", with: "'\\''") + "'"
    }
}
