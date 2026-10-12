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

    func testFinishedNeedsHumanRowOffersTalkOnlyWhileTheTicketStillWaits() throws {
        let s = try XCTUnwrap(StatusSnapshot.parse(Data("""
        {"groups":{"waiting":["W"],"ready_auto":["E"],"done":["D"]},
         "tickets":[{"id":"E","errored":"check-failed"},{"id":"W","status":"needs-human"},{"id":"D"}]}
        """.utf8)))
        func finished(_ ticket: String, _ result: String) throws -> FinishedTicket {
            let line = #"{"at":"2026-10-12 10:00 CEST","kind":"outcome","ticket":"\#(ticket)","attempts":1,"result":"\#(result)","detail":"q"}"#
            let rows = PanelHistory.rows(Data(line.utf8))
            guard case .ticket(let t)? = rows.first else { throw XCTSkip("no ticket row") }
            return t
        }
        XCTAssertTrue(s.canTalkThrough(finished: try finished("W", "needs-human")))
        XCTAssertFalse(s.canTalkThrough(finished: try finished("E", "needs-human")))  // answered: only the stale flag is left
        XCTAssertFalse(s.canTalkThrough(finished: try finished("D", "needs-human")))   // answered or closed since
        XCTAssertFalse(s.canTalkThrough(finished: try finished("W", "done")))          // only needs-human rows
        XCTAssertFalse(s.canTalkThrough(finished: try finished("W", "stopped")))
    }

    func testFinishedNeedsYouRowReadsAnsweredOnceTheTicketStopsWaiting() throws {
        // W still waits; E errored; R was answered (ready now); #8 was closed, so status no longer lists it.
        let s = try XCTUnwrap(StatusSnapshot.parse(Data("""
        {"groups":{"waiting":["W"],"ready_auto":["E","R"]},
         "tickets":[{"id":"W","status":"needs-human"},{"id":"E","errored":"check-failed"},{"id":"R"}]}
        """.utf8)))
        func finished(_ ticket: String, _ result: String) throws -> FinishedTicket {
            let line = #"{"at":"2026-10-12 10:00 CEST","kind":"outcome","ticket":"\#(ticket)","attempts":2,"result":"\#(result)","detail":"q"}"#
            guard case .ticket(let t)? = PanelHistory.rows(Data(line.utf8)).first else { throw XCTSkip("no ticket row") }
            return t
        }
        XCTAssertEqual(s.shownResult(try finished("W", "needs-human")), "needs-human")
        XCTAssertEqual(s.shownResult(try finished("E", "needs-human")), "needs-human")
        XCTAssertEqual(s.shownResult(try finished("R", "needs-human")), "answered")
        XCTAssertEqual(s.shownResult(try finished("#8", "needs-human")), "answered")
        XCTAssertEqual(s.shownResult(try finished("R", "done")), "done")
        XCTAssertEqual(s.shownResult(try finished("#8", "stopped")), "stopped")
    }

    func testBadgeCountsErroredTickets() {
        let a = ProjectStatus(label: "a", name: "a", state: .idle, detail: "", waiting: 2, errored: 1)
        let b = ProjectStatus(label: "b", name: "b", state: .idle, detail: "", waiting: 0)
        XCTAssertEqual(OverallState.badge([a, b]), 3)
    }
}
