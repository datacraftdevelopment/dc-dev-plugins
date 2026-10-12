import XCTest
@testable import RunwayCore

final class BoardTests: XCTestCase {
    private func queue() throws -> QueueStatus {
        let data = try Data(contentsOf: XCTUnwrap(Bundle.module.url(forResource: "status", withExtension: "json", subdirectory: "Fixtures")))
        return try XCTUnwrap(QueueStatus.parse(data))
    }

    private func runs(_ lines: [String]) -> [RunRecord] { RunsLog.parse(Data(lines.joined(separator: "\n").utf8)) }

    private func status(_ json: String) throws -> QueueStatus { try XCTUnwrap(QueueStatus.parse(Data(json.utf8))) }

    // MARK: columns

    func testEachGroupLandsInItsColumn() throws {
        let board = Board.build(queue: try queue())
        XCTAssertEqual(board.cards(.running).map(\.id), ["DAT-21"])
        XCTAssertEqual(board.cards(.needsYou).map(\.id), ["DAT-30"])
        XCTAssertEqual(board.cards(.upNext).map(\.id), ["DAT-22", "DAT-23", "DAT-31"])
        XCTAssertEqual(board.cards(.blocked).map(\.id), ["DAT-24"])
        XCTAssertEqual(board.cards(.done).map(\.id), [])  // status's done group is all-time; the board shows this round
    }

    func testNotesSayWhyACardIsWhereItIs() throws {
        let board = Board.build(queue: try queue())
        XCTAssertEqual(board.card("DAT-30")?.note, "Joe")
        XCTAssertEqual(board.card("DAT-30")?.waiting, true)
        XCTAssertEqual(board.card("DAT-22")?.note, "Next in line")
        XCTAssertNil(board.card("DAT-23")?.note)
        XCTAssertEqual(board.card("DAT-31")?.needsPrep, true)
        XCTAssertEqual(board.card("DAT-31")?.note, "A prep pass runs first")
        XCTAssertEqual(board.card("DAT-24")?.note, "Waits on DAT-22, DAT-23")
    }

    func testReasonWinsOverWaitingOn() throws {
        let q = try status(#"""
        {"version": 1, "groups": {"waiting": ["A"]},
         "tickets": [{"id": "A", "title": "a", "status": "needs-human", "gate": "human", "waiting_on": "Joe", "reason": "pick a theme"}]}
        """#)
        XCTAssertEqual(Board.build(queue: q).card("A")?.note, "pick a theme")
    }

    func testOnlyPrepReadyTicketIsNextAfterPrep() throws {
        let q = try status(#"""
        {"version": 1, "groups": {"ready_prep": ["P1", "P2"]},
         "tickets": [{"id": "P1", "title": "one", "gate": "human"}, {"id": "P2", "title": "two", "gate": "human"}]}
        """#)
        let board = Board.build(queue: q)
        XCTAssertEqual(board.card("P1")?.note, "Next in line, after a prep pass")
        XCTAssertEqual(board.card("P2")?.note, "A prep pass runs first")
    }

    func testErroredTicketsJoinNeedsYouAfterTheWaitingOnes() throws {
        let q = try status(#"""
        {"version": 1, "groups": {"waiting": ["W"], "running": ["R"], "blocked": ["E"], "done": ["D"]},
         "tickets": [{"id": "W", "title": "w", "status": "needs-human"},
                     {"id": "R", "title": "r", "status": "claimed", "errored": "check-failed"},
                     {"id": "E", "title": "e", "errored": "merge-conflict"},
                     {"id": "D", "title": "d", "status": "resolved", "errored": "agent-failed"}]}
        """#)
        let board = Board.build(queue: q)
        XCTAssertEqual(board.cards(.needsYou).map(\.id), ["W", "E"])  // running and done errored tickets stay put
        XCTAssertEqual(board.card("E")?.note, "merge conflict")
        XCTAssertEqual(board.card("E")?.waiting, false)
        XCTAssertEqual(board.cards(.running).map(\.id), ["R"])
        XCTAssertEqual(board.cards(.blocked).map(\.id), [])
    }

    func testLiveTicketMovesToRunningEvenBeforeStatusCatchesUp() throws {
        let board = Board.build(queue: try queue(), liveTicket: "DAT-22")
        XCTAssertEqual(board.cards(.running).map(\.id), ["DAT-22", "DAT-21"])
        XCTAssertEqual(board.cards(.upNext).map(\.id), ["DAT-23", "DAT-31"])
        XCTAssertEqual(board.card("DAT-23")?.note, "Next in line")  // the first card left in Up next, not DAT-22's old slot
    }

    func testLiveTicketLeadsRunningWhenStatusListsItSecond() throws {
        let q = try status(#"""
        {"version": 1, "groups": {"running": ["R1", "R2"]},
         "tickets": [{"id": "R1", "title": "one", "status": "claimed"}, {"id": "R2", "title": "two", "status": "claimed"}]}
        """#)
        XCTAssertEqual(Board.build(queue: q, liveTicket: "R2").cards(.running).map(\.id), ["R2", "R1"])
    }

    func testLiveTicketStatusDoesNotKnowStillShowsAsRunning() throws {
        let stale = Board.build(queue: try queue(), liveTicket: "DAT-99")
        XCTAssertEqual(stale.cards(.running).map(\.id), ["DAT-99", "DAT-21"])
        XCTAssertNil(stale.card("DAT-99")?.ticket)
        let none = Board.build(queue: nil, liveTicket: "DAT-99")
        XCTAssertEqual(none.cards(.running).map(\.id), ["DAT-99"])
    }

    func testAnsweredTicketStatusDroppedStaysInNeedsYou() throws {
        let gone = QueueTicket(id: "DAT-77", title: "Gone", url: nil, status: "needs-human", gate: "human", blockedBy: [],
                               waitingOn: nil, harness: nil, packet: "pick one")
        let moved = try XCTUnwrap(try queue().tickets.first { $0.id == "DAT-22" })
        let board = Board.build(queue: try queue(), answered: [gone, moved])
        XCTAssertEqual(board.cards(.needsYou).map(\.id), ["DAT-30", "DAT-77"])
        XCTAssertEqual(board.card("DAT-77")?.note, "Answered")
        XCTAssertEqual(board.card("DAT-77")?.waiting, false)
        XCTAssertEqual(board.card("DAT-22")?.column, .upNext)  // status still lists it, so it stays where status puts it
        XCTAssertEqual(BoardStats.make(board: board, runs: [], now: Date()).needsYou, 1)  // an answered card isn't waiting
    }

    /// A "no" that resolves the ticket: status lists it as done, no run merged it, so only the answer keeps it on the board.
    func testAnsweredTicketResolvedWithoutAMergeStaysInNeedsYou() throws {
        let q = try status(#"""
        {"version": 1, "groups": {"done": ["A"]},
         "tickets": [{"id": "A", "title": "Drop it", "status": "resolved", "gate": "human"}]}
        """#)
        let answered = try XCTUnwrap(q.tickets.first)
        let board = Board.build(queue: q, answered: [answered])
        XCTAssertEqual(board.card("A")?.column, .needsYou)
        XCTAssertEqual(board.card("A")?.note, "Answered")
        XCTAssertEqual(Board.build(queue: q).card("A"), nil)  // without the answer it has no column
    }

    /// Go, then a refresh in which status has dropped the ticket: the card and its answer are still on the board.
    @MainActor func testAnswerThenRefreshKeepsTheAnsweredCard() async throws {
        let first = try String(contentsOf: XCTUnwrap(Bundle.module.url(forResource: "status", withExtension: "json", subdirectory: "Fixtures")), encoding: .utf8)
        let gone = #"{"version": 1, "groups": {"waiting": []}, "tickets": []}"#
        let statusCommand = Command(executable: "/usr/bin/env", arguments: ["status"])
        let answerCommand = Command(executable: "/usr/bin/env", arguments: ["go"])
        let calls = StatusCalls()
        let feed = DecisionsFeed(run: { command in
            guard command == statusCommand else { return CommandResult(status: 0, stdout: "", stderr: "") }
            return CommandResult(status: 0, stdout: await calls.next() == 1 ? first : gone, stderr: "")
        })
        await feed.refresh(statusCommand)
        let ticket = try XCTUnwrap(feed.queue?.decisions.first)
        await feed.answer(ticket, go: true, note: "", command: answerCommand, status: statusCommand)

        let board = Board.build(queue: feed.queue, answered: feed.cards.filter { $0.answer != nil }.map(\.ticket))
        let card = try XCTUnwrap(board.card("DAT-30"))
        XCTAssertEqual(card.column, .needsYou)
        XCTAssertEqual(card.note, "Answered")
        XCTAssertNotNil(feed.answers[card.id])
    }

    func testNoStatusIsAnEmptyBoard() {
        let board = Board.build(queue: nil)
        for column in BoardColumn.allCases { XCTAssertTrue(board.cards(column).isEmpty) }
    }

    // MARK: this round

    func testDoneThisRoundComesFromOutcomesSinceTheLastFinish() throws {
        let log = runs([
            #"{"at": "2026-10-12T09:00:00Z", "kind": "outcome", "ticket": "DAT-20", "result": "done"}"#,
            #"{"at": "2026-10-12T10:00:00Z", "kind": "finish", "ticket": "finish", "check_exit": 0}"#,
            #"{"at": "2026-10-12T11:00:00Z", "kind": "run", "ticket": "DAT-22", "attempt": 1, "exit": 1, "secs": 300, "cost_usd": 0.5}"#,
            #"{"at": "2026-10-12T11:10:00Z", "kind": "run", "ticket": "DAT-22", "attempt": 2, "exit": 0, "secs": 540, "cost_usd": 0.75}"#,
            #"{"at": "2026-10-12T11:20:00Z", "kind": "outcome", "ticket": "DAT-22", "result": "done"}"#,
            #"{"at": "2026-10-12T11:30:00Z", "kind": "outcome", "ticket": "DAT-23", "result": "needs-human"}"#,
            #"{"at": "2026-10-12T11:40:00Z", "kind": "outcome", "ticket": "X-9", "result": "done"}"#,
        ])
        let board = Board.build(queue: try queue(), runs: log)
        XCTAssertEqual(board.cards(.done).map(\.id), ["X-9"])  // DAT-22 is already placed in Up next by status
        let merged = RoundLog.merged(log)
        XCTAssertEqual(merged.map(\.ticket), ["X-9", "DAT-22"])
        XCTAssertEqual(merged[1].note, "14 min · $1.25")
        XCTAssertNil(merged[0].note)
        XCTAssertEqual(board.card("X-9")?.title, "")  // status no longer lists it; the view shows the id
    }

    func testHistoryIsOneTicketsStepsOldestFirst() {
        let log = runs([
            #"{"at": "1", "kind": "prep", "ticket": "A", "exit": 0}"#,
            #"{"at": "2", "kind": "run", "ticket": "A", "attempt": 1, "exit": 0}"#,
            #"{"at": "3", "kind": "check", "ticket": "A", "attempt": 1, "exit": 1}"#,
            #"{"at": "4", "kind": "review", "ticket": "finish", "exit": 0}"#,
            #"{"at": "5", "kind": "run", "ticket": "B", "attempt": 1, "exit": 0}"#,
            #"{"at": "6", "kind": "outcome", "ticket": "A", "result": "needs-human"}"#,
        ])
        XCTAssertEqual(RoundLog.history("A", in: log).map(\.at), ["1", "2", "3", "6"])
        XCTAssertEqual(RoundLog.history("A", in: log, limit: 2).map(\.at), ["3", "6"])
    }

    // MARK: stats

    func testStatsCountTodayOnly() throws {
        let log = runs([
            #"{"at": "2026-10-11T23:00:00Z", "kind": "run", "ticket": "A", "exit": 0, "cost_usd": 9.0, "usage": {"input_tokens": 1000, "output_tokens": 0}}"#,
            #"{"at": "2026-10-12T08:00:00Z", "kind": "run", "ticket": "A", "exit": 0, "cost_usd": 1.5, "usage": {"input_tokens": 1200, "output_tokens": 300}}"#,
            #"{"at": "2026-10-12T09:00:00.250Z", "kind": "prep", "ticket": "B", "exit": 0, "cost_usd": 0.25}"#,
            #"{"at": "2026-10-12T09:30:00Z", "kind": "outcome", "ticket": "A", "result": "done"}"#,
        ])
        var utc = Calendar(identifier: .gregorian)
        utc.timeZone = TimeZone(identifier: "UTC")!
        let now = ISO8601DateFormatter().date(from: "2026-10-12T12:00:00Z")!
        let board = Board.build(queue: try queue(), runs: log)
        let stats = BoardStats.make(board: board, runs: log, now: now, calendar: utc)
        XCTAssertEqual(stats.spendToday, 1.75, accuracy: 0.001)
        XCTAssertEqual(stats.tokensToday, 1500)
        XCTAssertEqual(stats.mergedThisRound, 1)  // A merged this round
        XCTAssertEqual(stats.needsYou, 1)
    }

    func testTokenText() {
        XCTAssertEqual(BoardStats.tokens(512), "512")
        XCTAssertEqual(BoardStats.tokens(820_400), "820k")
        XCTAssertEqual(BoardStats.tokens(1_940_000), "1.9M")
    }
}

private actor StatusCalls {
    private var n = 0
    func next() -> Int { n += 1; return n }
}
