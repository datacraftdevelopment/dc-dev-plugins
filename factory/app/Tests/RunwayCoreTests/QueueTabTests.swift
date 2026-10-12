import XCTest
@testable import RunwayCore

final class QueueTabTests: XCTestCase {
    private func fixture() -> Data {
        try! Data(contentsOf: Bundle.module.url(forResource: "status", withExtension: "json", subdirectory: "Fixtures")!)
    }

    private let t0 = ISO8601DateFormatter().date(from: "2026-10-07T12:00:00Z")!
    private let command = Command(executable: "/usr/bin/true", arguments: [])

    // MARK: decoding

    func testDecodesTicketsAndGroups() throws {
        let queue = try XCTUnwrap(QueueStatus.parse(fixture()))
        XCTAssertEqual(queue.tickets.count, 7)
        let running = try XCTUnwrap(queue.tickets.first { $0.id == "DAT-21" })
        XCTAssertEqual(running.title, "Queue tab")
        XCTAssertEqual(running.url, "https://linear.app/x/DAT-21")
        XCTAssertEqual(running.harness, "codex")
        XCTAssertEqual(running.gate, "auto")
        XCTAssertNil(queue.tickets.first { $0.id == "DAT-23" }?.url)
        XCTAssertNil(queue.tickets.first { $0.id == "DAT-31" }?.harness)  // harness is optional
    }

    func testRejectsGarbageAndNewerVersions() {
        XCTAssertNil(QueueStatus.parse(Data("nope".utf8)))
        XCTAssertNil(QueueStatus.parse(Data(#"{"version": 2, "groups": {}, "tickets": []}"#.utf8)))
    }

    // MARK: sections

    func testSectionsFollowQueueOrder() throws {
        let sections = try XCTUnwrap(QueueStatus.parse(fixture())).sections
        XCTAssertEqual(sections.runsNext.map(\.id), ["DAT-21", "DAT-22", "DAT-23"])
        XCTAssertEqual(sections.waiting.map(\.id), ["DAT-30", "DAT-31"])
        XCTAssertEqual(sections.blocked.map(\.id), ["DAT-24"])
        XCTAssertEqual(sections.done.map(\.id), ["DAT-20"])
    }

    func testBlockedRowSaysWhatBlocksIt() throws {
        let blocked = try XCTUnwrap(QueueStatus.parse(fixture())).sections.blocked[0]
        XCTAssertEqual(blocked.blockedBy, ["DAT-22", "DAT-23"])
    }


    // MARK: queue plan fields (next_step, reason, run_now, idle_reason, finish)

    private func planJSON(runNow: String?, idle: String?) -> Data {
        func q(_ s: String?) -> String { s.map { "\"\($0)\"" } ?? "null" }
        return Data("""
        {"version": 1, "run_now": \(q(runNow)), "idle_reason": \(q(idle)),
         "finish": {"verdict": "wait", "reason": "2 open under all_done"},
         "groups": {"waiting": ["T/07"], "ready_auto": ["T/21"], "blocked": ["T/22"], "running": [], "ready_prep": [], "done": []},
         "tickets": [
          {"id": "T/07", "title": "Decide", "status": "needs-human", "gate": "human", "next_step": "waiting", "reason": "waits on you"},
          {"id": "T/21", "title": "Build", "status": "ready", "gate": "auto", "next_step": "queued", "reason": "after T/07", "blocked_by": ["T/07"]},
          {"id": "T/22", "title": "More", "status": "ready", "gate": "auto", "next_step": "blocked", "reason": "waits on T/21", "blocked_by": ["T/21"]}]}
        """.utf8)
    }

    func testParsesPlanFields() throws {
        let queue = try XCTUnwrap(QueueStatus.parse(planJSON(runNow: "T/21", idle: nil)))
        XCTAssertEqual(queue.runNow, "T/21")
        XCTAssertNil(queue.idleReason)
        XCTAssertEqual(queue.finish, QueueFinish(verdict: "wait", reason: "2 open under all_done"))
        XCTAssertEqual(queue.tickets.first { $0.id == "T/22" }?.nextStep, "blocked")
        XCTAssertEqual(queue.tickets.first { $0.id == "T/22" }?.reason, "waits on T/21")
        XCTAssertTrue(queue.hasPlan)
    }

    func testOlderEngineHasNoPlan() throws {
        let queue = try XCTUnwrap(QueueStatus.parse(fixture()))
        XCTAssertFalse(queue.hasPlan)
        XCTAssertNil(queue.runNow)
        XCTAssertNil(queue.finish)
        XCTAssertNil(queue.tickets.first?.nextStep)
        XCTAssertNil(queue.banner)
    }

    func testNothingRunsShowsIdleReasonAndMarksNoTicket() throws {
        let queue = try XCTUnwrap(QueueStatus.parse(planJSON(runNow: nil, idle: "Nothing can run: 19 tickets wait on #7")))
        XCTAssertEqual(queue.banner?.headline, "Nothing can run: 19 tickets wait on #7")
        XCTAssertEqual(queue.banner?.finish, "Finish waits: 2 open under all_done")
        let board = Board.build(queue: queue)
        XCTAssertTrue(board.cards(.upNext).allSatisfy { !$0.runsNext })
        XCTAssertNotEqual(board.card("T/21")?.note, "Next in line")
    }

    func testRunNowIsMarkedAndBannerNamesIt() throws {
        let queue = try XCTUnwrap(QueueStatus.parse(planJSON(runNow: "T/21", idle: nil)))
        XCTAssertEqual(queue.banner?.headline, "Runs next: T/21 Build")
        let board = Board.build(queue: queue)
        XCTAssertEqual(board.cards(.upNext).filter(\.runsNext).map(\.id), ["T/21"])
    }

    func testWaitingAndBlockedCardsCarryTheEnginesReason() throws {
        let board = Board.build(queue: try XCTUnwrap(QueueStatus.parse(planJSON(runNow: nil, idle: "x"))))
        XCTAssertEqual(board.card("T/07")?.note, "waits on you")
        XCTAssertEqual(board.card("T/22")?.note, "waits on T/21")
    }

    func testOlderEngineBoardStillMarksFirstReady() throws {
        let board = Board.build(queue: try XCTUnwrap(QueueStatus.parse(fixture())))
        XCTAssertEqual(board.cards(.upNext).first?.note, "Next in line")
        XCTAssertEqual(board.card("DAT-24")?.note, "Waits on DAT-22, DAT-23")
    }

    // MARK: age

    func testAgeText() {
        XCTAssertEqual(QueueFeed.ageText(from: t0, now: t0.addingTimeInterval(4)), "just now")
        XCTAssertEqual(QueueFeed.ageText(from: t0, now: t0.addingTimeInterval(90)), "1m ago")
        XCTAssertEqual(QueueFeed.ageText(from: t0, now: t0.addingTimeInterval(7300)), "2h ago")
        XCTAssertEqual(QueueFeed.ageText(from: t0, now: t0.addingTimeInterval(-5)), "just now")
    }

    // MARK: refresh

    @MainActor func testRefreshKeepsLastGoodResultAndShowsTheError() async {
        let good = CommandResult(status: 0, stdout: String(decoding: fixture(), as: UTF8.self), stderr: "")
        let bad = CommandResult(status: 1, stdout: "", stderr: "LINEAR_API_KEY rejected")
        let results = Results([good, bad])
        let clock = Clock(t0)
        let feed = QueueFeed(run: { _ in await results.next() }, now: { clock.date })

        await feed.refresh(command)
        XCTAssertEqual(feed.queue?.tickets.count, 7)
        XCTAssertNil(feed.error)
        XCTAssertEqual(feed.fetchedAt, t0)

        clock.date = t0.addingTimeInterval(120)
        await feed.refresh(command)
        XCTAssertEqual(feed.error, "LINEAR_API_KEY rejected")
        XCTAssertEqual(feed.queue?.tickets.count, 7, "last good result stays")
        XCTAssertEqual(feed.fetchedAt, t0, "age counts from the last good fetch")
    }

    @MainActor func testUnparseableOutputIsAnError() async {
        let t0 = self.t0
        let feed = QueueFeed(run: { _ in CommandResult(status: 0, stdout: "<html>", stderr: "") }, now: { t0 })
        await feed.refresh(command)
        XCTAssertNotNil(feed.error)
        XCTAssertNil(feed.queue)
    }

    @MainActor func testRefreshDoesNotHoldTheMainActor() async {
        let t0 = self.t0
        let feed = QueueFeed(run: { _ in
            try? await Task.sleep(nanoseconds: 300_000_000)
            return CommandResult(status: 1, stdout: "", stderr: "slow")
        }, now: { t0 })
        let refresh = Task { await feed.refresh(command) }
        try? await Task.sleep(nanoseconds: 50_000_000)  // only possible if refresh suspended off the main actor
        XCTAssertTrue(feed.isRefreshing)
        await refresh.value
        XCTAssertFalse(feed.isRefreshing)
    }

    @MainActor func testOverlappingRefreshesRunOnce() async {
        let t0 = self.t0
        let calls = Counter()
        let feed = QueueFeed(run: { _ in
            await calls.bump()
            try? await Task.sleep(nanoseconds: 100_000_000)
            return CommandResult(status: 1, stdout: "", stderr: "x")
        }, now: { t0 })
        async let a: Void = feed.refresh(command)
        async let b: Void = feed.refresh(command)
        _ = await (a, b)
        let count = await calls.count
        XCTAssertEqual(count, 1)
    }
}

private actor Results {
    private var items: [CommandResult]
    init(_ items: [CommandResult]) { self.items = items }
    func next() -> CommandResult { items.removeFirst() }
}

private actor Counter {
    private(set) var count = 0
    func bump() { count += 1 }
}

private final class Clock: @unchecked Sendable {
    var date: Date
    init(_ date: Date) { self.date = date }
}
