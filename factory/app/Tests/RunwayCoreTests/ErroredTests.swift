import XCTest
@testable import RunwayCore

final class ErroredTests: XCTestCase {
    private let tools = RunwayTools(scheduleScript: "/x/schedule.sh", runwayScript: "/Users/me/My Plugins/runway.py")

    /// The shell command inside the `do script "..."` line of an osascript command.
    private func script(_ command: Command) throws -> String {
        XCTAssertEqual(command.executable, "/usr/bin/osascript")
        XCTAssertTrue(command.arguments.contains("tell application \"Terminal\" to activate"))
        let line = try XCTUnwrap(command.arguments.last)
        let prefix = "tell application \"Terminal\" to do script \""
        XCTAssertTrue(line.hasPrefix(prefix) && line.hasSuffix("\""))
        // What Terminal receives once AppleScript has read the string literal.
        return String(line.dropFirst(prefix.count).dropLast())
            .replacingOccurrences(of: "\\\"", with: "\"").replacingOccurrences(of: "\\\\", with: "\\")
    }

    func testDiscussCommandQuotesRepoScriptAndIdWithSpaceAndSingleQuote() throws {
        let command = tools.discuss(ticket: "GH 5'x", repo: "/Users/me/Joe's Repo")
        XCTAssertEqual(try script(command),
                       #"cd '/Users/me/Joe'\''s Repo' && python3 '/Users/me/My Plugins/runway.py' discuss 'GH 5'\''x'"#)
    }

    func testDiscussLoopCommandNamesDiscussLoop() throws {
        let command = tools.discussLoop(repo: "/Users/me/My Repo")
        XCTAssertEqual(try script(command),
                       "cd '/Users/me/My Repo' && python3 '/Users/me/My Plugins/runway.py' discuss --loop")
    }

    func testDoubleQuoteAndBackslashAreEscapedForAppleScript() throws {
        let line = try XCTUnwrap(tools.discuss(ticket: #"a"b\c"#, repo: "/r").arguments.last)
        XCTAssertTrue(line.contains(#"'a\"b\\c'"#), line)
    }

    func testErroredParsesFromStatusAndMissingMeansNotErrored() throws {
        let q = try XCTUnwrap(QueueStatus.parse(Data("""
        {"version":1,"groups":{"ready_auto":["A","B"]},
         "tickets":[{"id":"A","title":"a","errored":"check-failed"},{"id":"B","title":"b"}]}
        """.utf8)))
        XCTAssertEqual(q.tickets[0].errored, "check-failed")
        XCTAssertNil(q.tickets[1].errored)
        let s = try XCTUnwrap(StatusSnapshot.parse(Data("""
        {"groups":{"ready_auto":["A","B"]},"tickets":[{"id":"A","errored":"merge-conflict"},{"id":"B"}]}
        """.utf8)))
        XCTAssertEqual(s.errored, ["A": "merge-conflict"])
    }

    func testEveryKindMapsToWords() {
        XCTAssertEqual(ErroredKind.words("check-failed"), "check failed")
        XCTAssertEqual(ErroredKind.words("merge-conflict"), "merge conflict")
        XCTAssertEqual(ErroredKind.words("agent-failed"), "agent failed")
        XCTAssertEqual(ErroredKind.words("no-commits"), "no commits")
        XCTAssertEqual(ErroredKind.words("signed-out"), "signed out")
        XCTAssertEqual(ErroredKind.words("something-new"), "something new")
    }

    func testErroredTicketsJoinNeedsYouUnderTheWaitingOnes() throws {
        let s = try XCTUnwrap(StatusSnapshot.parse(Data("""
        {"groups":{"waiting":["W"],"ready_auto":["E"],"done":["D"]},
         "tickets":[{"id":"E","title":"err","errored":"no-commits"},
                    {"id":"W","title":"wait","status":"needs-human","errored":"agent-failed"},
                    {"id":"D","title":"done"}]}
        """.utf8)))
        XCTAssertEqual(s.needsYou.map(\.id), ["W", "E"])
        XCTAssertEqual(s.needsYou.map(\.errored), ["agent-failed", "no-commits"])
        XCTAssertEqual(s.erroredOnlyCount, 1)
    }

    func testTalkItThroughIsOfferedForWaitingAndErroredTicketsOnly() throws {
        let s = try XCTUnwrap(StatusSnapshot.parse(Data("""
        {"groups":{"waiting":["W"],"ready_auto":["E","R"],"done":["D"]},
         "tickets":[{"id":"E","errored":"check-failed"},{"id":"W","status":"needs-human"},{"id":"R"},{"id":"D"}]}
        """.utf8)))
        XCTAssertTrue(s.canTalkThrough("W"))
        XCTAssertTrue(s.canTalkThrough("E"))
        XCTAssertFalse(s.canTalkThrough("R"))
        XCTAssertFalse(s.canTalkThrough("D"))
        XCTAssertFalse(s.canTalkThrough("unknown"))
    }

    func testBadgeCountsErroredTickets() {
        let a = ProjectStatus(label: "a", name: "a", state: .idle, detail: "", waiting: 2, errored: 1)
        let b = ProjectStatus(label: "b", name: "b", state: .idle, detail: "", waiting: 0)
        XCTAssertEqual(OverallState.badge([a, b]), 3)
    }
}
