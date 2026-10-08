import XCTest
@testable import RunwayCore

final class PanelHistoryTests: XCTestCase {
    private func data(_ lines: [String]) -> Data { Data(lines.joined(separator: "\n").utf8) }

    private func run(_ ticket: String, at: String, attempt: Int = 1, secs: Int, cost: Double, input: Int, output: Int,
                     exit: Int = 0, kind: String = "run") -> String {
        #"{"at":"2026-10-08 \#(at) EDT","kind":"\#(kind)","ticket":"\#(ticket)","attempt":\#(attempt),"harness":"claude","exit":\#(exit),"secs":\#(secs),"session_id":"s-\#(ticket)-\#(attempt)","cost_usd":\#(cost),"num_turns":10,"usage":{"input_tokens":\#(input),"output_tokens":\#(output)}}"#
    }

    private func outcome(_ ticket: String, at: String, attempts: Int = 1, result: String = "done", detail: String = "") -> String {
        #"{"at":"2026-10-08 \#(at) EDT","kind":"outcome","ticket":"\#(ticket)","attempts":\#(attempts),"result":"\#(result)","detail":"\#(detail)"}"#
    }

    private var log: [String] {
        [
            run("DAT-35", at: "16:30", secs: 3, cost: 0, input: 0, output: 0, exit: 1),
            outcome("DAT-35", at: "16:30"),
            run("DAT-36", at: "16:32", secs: 3, cost: 0, input: 0, output: 0, exit: 1),
            outcome("DAT-36", at: "16:32"),
            run("DAT-40", at: "16:47", secs: 177, cost: 0.78, input: 36, output: 20612),
            outcome("DAT-40", at: "16:49"),
            run("DAT-42", at: "16:53", secs: 257, cost: 1.20, input: 62, output: 26773),
            run("DAT-42", at: "16:54", attempt: 2, secs: 31, cost: 0.31, input: 22, output: 2663),
            outcome("DAT-42", at: "16:56", attempts: 2, detail: "Check failed on attempt 1"),
        ]
    }

    func testTicketsNewestFirstWithTheirCalls() {
        let rows = PanelHistory.rows(data(log))
        guard case .ticket(let latest) = rows.first else { return XCTFail("expected a ticket row first") }
        XCTAssertEqual(latest.ticket, "DAT-42")
        XCTAssertEqual(latest.attempts, 2)
        XCTAssertEqual(latest.steps.map(\.attempt), [1, 2])
        XCTAssertEqual(latest.agentSecs, 288)
        XCTAssertEqual(latest.costUSD, 1.51, accuracy: 1e-9)
        XCTAssertEqual(latest.tokens, 62 + 26773 + 22 + 2663)
        XCTAssertEqual(latest.turns, 20)
        XCTAssertEqual(latest.detail, "Check failed on attempt 1")
        XCTAssertFalse(latest.noWork)
    }

    func testWallTimeRunsFromFirstCallStartToOutcome() throws {
        guard case .ticket(let t) = PanelHistory.rows(data(log)).first else { return XCTFail() }
        // First call ended 16:53 after 257s, so it began 16:48:43; outcome at 16:56 → 437s.
        XCTAssertEqual(try XCTUnwrap(t.wallSecs), 437, accuracy: 1)
        XCTAssertEqual(PanelHistory.duration(try XCTUnwrap(t.wallSecs)), "7m")
    }

    func testWallTimeIsNeverShorterThanAgentTime() throws {
        // Minute stamps: a 100s call ending 12:00 and an outcome stamped 12:00 would give 100s, not less.
        let rows = PanelHistory.rows(data([
            run("A", at: "12:00", secs: 100, cost: 0.1, input: 1, output: 1),
            run("A", at: "12:00", attempt: 2, secs: 80, cost: 0.1, input: 1, output: 1),
            outcome("A", at: "12:00", attempts: 2),
        ]))
        guard case .ticket(let t) = rows.first else { return XCTFail() }
        XCTAssertEqual(try XCTUnwrap(t.wallSecs), 180, accuracy: 0.001)
    }

    func testNoWorkTicketsFoldIntoOneRow() {
        let rows = PanelHistory.rows(data(log))
        XCTAssertEqual(rows.count, 3)
        guard case .noWork(let group) = rows[2] else { return XCTFail("expected the no-work group last") }
        XCTAssertEqual(group.map(\.ticket), ["DAT-36", "DAT-35"])
        XCTAssertTrue(group.allSatisfy(\.noWork))
    }

    func testALoneNoWorkTicketIsStillFlagged() {
        let rows = PanelHistory.rows(data([run("X", at: "10:00", secs: 3, cost: 0, input: 0, output: 0, exit: 1),
                                           outcome("X", at: "10:00")]))
        guard case .noWork(let group) = rows.first else { return XCTFail() }
        XCTAssertEqual(group.map(\.ticket), ["X"])
    }

    func testParkedTicketWithNoTokensIsNotNoWork() {
        // needs-human with nothing spent is a real outcome, not a false "done".
        let rows = PanelHistory.rows(data([run("P", at: "10:00", secs: 3, cost: 0, input: 0, output: 0, exit: 1),
                                           outcome("P", at: "10:01", result: "needs-human")]))
        guard case .ticket(let t) = rows.first else { return XCTFail() }
        XCTAssertEqual(t.result, "needs-human")
        XCTAssertFalse(t.noWork)
    }

    func testFinishRowCarriesItsReviewCalls() {
        let review = #"{"at":"2026-10-08 16:17 EDT","kind":"review","ticket":"finish","harness":"ringer-panel","exit":0,"cost_usd":0.4}"#
        let finish = #"{"at":"2026-10-08 16:18 EDT","kind":"finish","ticket":"finish","findings":true,"fix":"The fix pass made no changes; the findings stand.","check_exit":0,"pr":"_pm/runway-pr.md"}"#
        let rows = PanelHistory.rows(data(log + [review, finish]))
        guard case .finish(let f) = rows.first else { return XCTFail("expected the finish row first") }
        XCTAssertEqual(f.checkPassed, true)
        XCTAssertEqual(f.findings, true)
        XCTAssertEqual(f.pr, "_pm/runway-pr.md")
        XCTAssertEqual(f.costUSD, 0.4, accuracy: 1e-9)
        XCTAssertTrue(f.fix.hasPrefix("The fix pass"))
    }

    func testCallsWithoutAnOutcomeYetAreLeftOut() {
        let rows = PanelHistory.rows(data(log + [run("DAT-35", at: "17:01", secs: 280, cost: 0.6, input: 5, output: 9)]))
        guard case .ticket(let t) = rows.first else { return XCTFail() }
        XCTAssertEqual(t.ticket, "DAT-42")
    }

    func testLimitKeepsTheNewest() {
        let rows = PanelHistory.rows(data(log), limit: 1)
        XCTAssertEqual(rows.count, 1)
        guard case .ticket(let t) = rows.first else { return XCTFail() }
        XCTAssertEqual(t.ticket, "DAT-42")
    }

    func testBadLinesAreSkippedAndStayAligned() {
        let rows = PanelHistory.rows(data(["not json", "[1]", ""] + log))
        guard case .ticket(let t) = rows.first else { return XCTFail() }
        XCTAssertEqual(t.ticket, "DAT-42")
        XCTAssertEqual(t.steps.count, 2)
    }

    func testDaysSplitTodayYesterdayAndOlder() throws {
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = try XCTUnwrap(TimeZone(identifier: "America/New_York"))
        let now = try XCTUnwrap(PanelHistory.date("2026-10-08 17:05 EDT"))
        let lines = [
            #"{"at":"2026-10-06 09:00 EDT","kind":"run","ticket":"OLD","secs":60,"cost_usd":0.1,"usage":{"input_tokens":1,"output_tokens":1}}"#,
            #"{"at":"2026-10-06 09:01 EDT","kind":"outcome","ticket":"OLD","attempts":1,"result":"done"}"#,
            #"{"at":"2026-10-07 13:19 EDT","kind":"run","ticket":"Y","secs":140,"cost_usd":0.52,"usage":{"input_tokens":1,"output_tokens":1}}"#,
            #"{"at":"2026-10-07 13:19 EDT","kind":"outcome","ticket":"Y","attempts":1,"result":"done"}"#,
        ] + log
        let days = PanelHistory.days(PanelHistory.rows(data(lines)), now: now, calendar: calendar)
        XCTAssertEqual(days.map(\.label).prefix(2), ["Today", "Yesterday"])
        XCTAssertEqual(days.count, 3)
        XCTAssertEqual(PanelHistory.doneCount(days[0].rows), 2)  // DAT-42 and DAT-40; the no-work pair doesn't count
        XCTAssertEqual(PanelHistory.cost(of: days[0].rows), 2.29, accuracy: 1e-9)
        XCTAssertEqual(PanelHistory.doneCount(days[1].rows), 1)
        XCTAssertEqual(days[2].label, "Tue 6 Oct")
    }

    func testFormatting() {
        XCTAssertEqual(PanelHistory.duration(45), "45s")
        XCTAssertEqual(PanelHistory.duration(437), "7m")
        XCTAssertEqual(PanelHistory.duration(4320), "1h 12m")
        XCTAssertEqual(PanelHistory.cost(0), "$0")
        XCTAssertEqual(PanelHistory.cost(1.5077), "$1.51")
        XCTAssertEqual(PanelHistory.tokens(850), "850")
        XCTAssertEqual(PanelHistory.tokens(29520), "29.5k")
        XCTAssertEqual(PanelHistory.tokens(1_250_000), "1.2M")
    }

    func testDateReadsTheEngineStampAndFallsBackToLocal() {
        XCTAssertNotNil(PanelHistory.date("2026-10-08 16:56 EDT"))
        XCTAssertNotNil(PanelHistory.date("2026-10-08 16:56 XYZT"))
        XCTAssertNil(PanelHistory.date("yesterday"))
    }

    // MARK: up next

    func testUpNextIsReadyThenPrepThenBlockedInStatusOrder() throws {
        let json = #"""
        {"version":1,"groups":{"waiting":[],"running":["DAT-35"],"ready_auto":["R1"],"ready_prep":["P1"],
          "blocked":["DAT-36","DAT-37"],"done":["DAT-9"]},
         "tickets":[{"id":"DAT-35","title":"Now"},{"id":"R1","title":"Ready one"},{"id":"P1","title":"Prep one"},
          {"id":"DAT-36","title":"Works an issue","blocked_by":["DAT-35"]},{"id":"DAT-37","title":"Decisions","blocked_by":["DAT-36"]},
          {"id":"DAT-9","title":"Old"}]}
        """#
        let snapshot = try XCTUnwrap(StatusSnapshot.parse(Data(json.utf8)))
        XCTAssertEqual(snapshot.upNext.map(\.id), ["R1", "P1", "DAT-36", "DAT-37"])
        XCTAssertEqual(snapshot.upNext.map(\.kind), [.ready, .prep, .blocked, .blocked])
        XCTAssertEqual(snapshot.upNext[2].title, "Works an issue")
        XCTAssertEqual(snapshot.upNext[2].blockedBy, ["DAT-35"])
    }
}
