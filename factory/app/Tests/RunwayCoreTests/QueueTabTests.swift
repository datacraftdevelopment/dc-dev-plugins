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
