import XCTest
@testable import RunwayCore

@MainActor
final class SessionTests: XCTestCase {
    private let tools = RunwayTools(scheduleScript: "/x/schedule.sh", runwayScript: "/Users/me/My Plugins/runway.py")

    /// The shell command inside the `do script "..."` line of the Terminal command.
    private func terminalShell(_ command: Command) -> String {
        let line = command.arguments.last ?? ""
        let prefix = "tell application \"Terminal\" to do script \""
        return String(line.dropFirst(prefix.count).dropLast())
            .replacingOccurrences(of: "\\\"", with: "\"").replacingOccurrences(of: "\\\\", with: "\\")
    }

    func testLaunchSpecForATicketIsTheTerminalCommandInALoginShellInTheRepo() {
        let spec = tools.discussSession(ticket: "GH 5'x", repo: "/Users/me/Joe's Repo")
        XCTAssertEqual(spec.executable, "/bin/zsh")
        XCTAssertEqual(spec.arguments, ["-lc",
            #"cd '/Users/me/Joe'\''s Repo' && python3 '/Users/me/My Plugins/runway.py' discuss 'GH 5'\''x'"#])
        XCTAssertEqual(spec.workingDirectory, "/Users/me/Joe's Repo")
        XCTAssertEqual(spec.arguments[1], terminalShell(tools.discuss(ticket: "GH 5'x", repo: "/Users/me/Joe's Repo")))
    }

    func testLaunchSpecForTheLoopMatchesDiscussLoop() {
        let spec = tools.discussLoopSession(repo: "/Users/me/My Repo")
        XCTAssertEqual(spec.arguments,
                       ["-lc", "cd '/Users/me/My Repo' && python3 '/Users/me/My Plugins/runway.py' discuss --loop"])
        XCTAssertEqual(spec.workingDirectory, "/Users/me/My Repo")
        XCTAssertEqual(spec.arguments[1], terminalShell(tools.discussLoop(repo: "/Users/me/My Repo")))
    }

    func testAnExistingLiveTabForTheSameTicketIsFocusedNotDuplicated() {
        let registry = SessionRegistry()
        let spec = tools.discussSession(ticket: "GH-7", repo: "/r")
        let first = registry.open(project: "p", ticket: "GH-7", spec: spec)
        let other = registry.open(project: "p", ticket: "GH-8", spec: tools.discussSession(ticket: "GH-8", repo: "/r"))
        XCTAssertEqual(registry.selected, other.id)
        let again = registry.open(project: "p", ticket: "GH-7", spec: spec)
        XCTAssertEqual(again.id, first.id)
        XCTAssertEqual(registry.sessions.count, 2)
        XCTAssertEqual(registry.selected, first.id)
        XCTAssertEqual(first.title, "GH-7")
    }

    func testANewTabStartsAfterTheProcessExitsAndTheLoopIsTitledLoop() {
        let registry = SessionRegistry()
        let spec = tools.discussSession(ticket: "GH-7", repo: "/r")
        let first = registry.open(project: "p", ticket: "GH-7", spec: spec)
        registry.markExited(first.id)
        XCTAssertEqual(registry.liveCount, 0)
        let second = registry.open(project: "p", ticket: "GH-7", spec: spec)
        XCTAssertNotEqual(second.id, first.id)
        XCTAssertEqual(registry.liveCount, 1)
        let loop = registry.open(project: "p", ticket: nil, spec: tools.discussLoopSession(repo: "/r"))
        XCTAssertEqual(loop.title, "loop")
        XCTAssertEqual(registry.open(project: "q", ticket: nil, spec: spec).title, "loop", "other project, own tab")
        XCTAssertEqual(registry.sessions.count, 4)
    }

    func testClosingATabRemovesItAndMovesTheSelection() {
        let registry = SessionRegistry()
        let a = registry.open(project: "p", ticket: "A", spec: tools.discussSession(ticket: "A", repo: "/r"))
        let b = registry.open(project: "p", ticket: "B", spec: tools.discussSession(ticket: "B", repo: "/r"))
        registry.close(b.id)
        XCTAssertEqual(registry.sessions.map(\.id), [a.id])
        XCTAssertEqual(registry.selected, a.id)
        registry.close(a.id)
        XCTAssertNil(registry.selected)
    }
}
