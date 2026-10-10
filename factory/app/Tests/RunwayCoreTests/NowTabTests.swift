import XCTest
@testable import RunwayCore

final class NowTabTests: XCTestCase {
    private let now = ISO8601DateFormatter().date(from: "2026-10-07T12:00:00Z")!

    private func beat(_ extra: [String: Any] = [:]) -> Heartbeat {
        var json: [String: Any] = ["version": 1, "phase": "agent", "ticket": "DAT-14", "attempt": 2, "pid": 1,
                                   "since": "2026-10-07T11:58:00Z", "tick_started": "2026-10-07T11:55:00Z",
                                   "last_result": "fail"]
        json.merge(extra) { $1 }
        return Heartbeat.parse(try! JSONSerialization.data(withJSONObject: json))!
    }

    // MARK: heartbeat fields

    func testHeartbeatCarriesAttemptTickStartAndResult() {
        let hb = beat()
        XCTAssertEqual(hb.attempt, 2)
        XCTAssertEqual(hb.tickStarted, now.addingTimeInterval(-300))
        XCTAssertEqual(hb.lastResult, "fail")
    }

    // MARK: dead pid

    func testDeadTickHasNoTimerAndNoHighlight() {
        XCTAssertNil(NowMath.elapsed(heartbeat: beat(), now: now, pidAlive: { _ in false }))
        let strip = NowMath.phaseStrip(heartbeat: beat(), pidAlive: { _ in false })
        XCTAssertTrue(strip.allSatisfy { $0.state == .todo })
    }

    func testLiveTickDrawsAsBefore() {
        XCTAssertEqual(NowMath.elapsed(heartbeat: beat(), now: now, pidAlive: { _ in true }), 300)
        let strip = NowMath.phaseStrip(heartbeat: beat(["phase": "agent"]), pidAlive: { _ in true })
        XCTAssertEqual(strip.map(\.state), [.done, .done, .current, .todo, .todo])
    }

    func testMissingPidTickDrawsAsLive() {
        let hb = beat(["pid": NSNull()])
        XCTAssertEqual(NowMath.elapsed(heartbeat: hb, now: now, pidAlive: { _ in false }), 300)
    }

    // MARK: elapsed

    func testElapsedRunsFromTickStart() {
        XCTAssertEqual(NowMath.elapsed(heartbeat: beat(), now: now), 300)
    }

    func testElapsedFallsBackToPhaseStart() {
        XCTAssertEqual(NowMath.elapsed(heartbeat: beat(["tick_started": NSNull()]), now: now), 120)
    }

    func testElapsedIsNilWhenNotInATick() {
        XCTAssertNil(NowMath.elapsed(heartbeat: beat(["phase": "idle"]), now: now))
        XCTAssertNil(NowMath.elapsed(heartbeat: nil, now: now))
    }

    func testElapsedNeverNegative() {
        XCTAssertEqual(NowMath.elapsed(heartbeat: beat(["tick_started": "2026-10-07T12:05:00Z"]), now: now), 0)
    }

    func testClockText() {
        XCTAssertEqual(NowMath.clock(0), "0:00")
        XCTAssertEqual(NowMath.clock(65), "1:05")
        XCTAssertEqual(NowMath.clock(3725), "1:02:05")
    }

    // MARK: next tick

    func testNextTickIsLastRunPlusInterval() {
        let last = now.addingTimeInterval(-120)
        XCTAssertEqual(NowMath.nextTick(lastRun: last, interval: 600, loopOn: true, now: now),
                       .at(last.addingTimeInterval(600)))
    }

    func testNextTickDueWhenIntervalHasPassed() {
        XCTAssertEqual(NowMath.nextTick(lastRun: now.addingTimeInterval(-700), interval: 600, loopOn: true, now: now), .due)
    }

    func testNextTickUnknownWithoutARunOrInterval() {
        XCTAssertEqual(NowMath.nextTick(lastRun: nil, interval: 600, loopOn: true, now: now), .unknown)
        XCTAssertEqual(NowMath.nextTick(lastRun: now, interval: nil, loopOn: true, now: now), .unknown)
    }

    func testNextTickIsNoneWhenLoopOff() {
        XCTAssertEqual(NowMath.nextTick(lastRun: now, interval: 600, loopOn: false, now: now), .none)
    }

    func testNextTickText() {
        XCTAssertEqual(NowMath.text(.at(now.addingTimeInterval(95)), now: now), "in 1:35")
        XCTAssertEqual(NowMath.text(.due, now: now), "due now")
        XCTAssertEqual(NowMath.text(.unknown, now: now), "—")
        XCTAssertEqual(NowMath.text(.none, now: now), "loop off")
    }

    // MARK: phase strip

    func testPhaseStripMarksDoneCurrentAndTodo() {
        let strip = NowMath.phaseStrip(heartbeat: beat(["phase": "check"]))
        XCTAssertEqual(strip.map(\.name), ["sync", "prep", "agent", "check", "merge"])
        XCTAssertEqual(strip.map(\.state), [.done, .done, .done, .current, .todo])
    }

    func testPhaseStripAllTodoWhenIdleOrMissing() {
        XCTAssertEqual(NowMath.phaseStrip(heartbeat: beat(["phase": "idle"])).map(\.state), Array(repeating: .todo, count: 5))
        XCTAssertEqual(NowMath.phaseStrip(heartbeat: nil).map(\.state), Array(repeating: .todo, count: 5))
    }

    func testFinishPhaseShowsEverythingDone() {
        XCTAssertEqual(NowMath.phaseStrip(heartbeat: beat(["phase": "finish"])).map(\.state), Array(repeating: .done, count: 5))
    }

    // MARK: banners

    func testBanners() {
        XCTAssertEqual(NowMath.banners(loopOn: false, readyCount: 3, waiting: 0, paused: false), [.loopOffReady(3)])
        XCTAssertEqual(NowMath.banners(loopOn: true, readyCount: 3, waiting: 2, paused: true),
                       [.decisionsWaiting(2), .paused])
        XCTAssertEqual(NowMath.banners(loopOn: false, readyCount: 0, waiting: 0, paused: false), [])
    }

    // MARK: log tail

    private func tempLog() -> URL {
        FileManager.default.temporaryDirectory.appendingPathComponent("runway-\(UUID().uuidString).log")
    }

    private func append(_ text: String, to url: URL) {
        if let handle = try? FileHandle(forWritingTo: url) {
            handle.seekToEndOfFile()
            handle.write(Data(text.utf8))
            try? handle.close()
        } else {
            try! Data(text.utf8).write(to: url)
        }
    }

    func testLogTailMissingFileIsEmpty() {
        var tail = LogTail(url: tempLog(), maxLines: 30)
        XCTAssertFalse(tail.poll())
        XCTAssertEqual(tail.lines, [])
    }

    func testLogTailReadsOnlyNewBytes() {
        let url = tempLog()
        defer { try? FileManager.default.removeItem(at: url) }
        append("one\ntwo\n", to: url)
        var tail = LogTail(url: url, maxLines: 30)
        XCTAssertTrue(tail.poll())
        XCTAssertEqual(tail.lines, ["one", "two"])
        XCTAssertEqual(tail.bytesRead, 8)

        XCTAssertFalse(tail.poll())  // nothing new
        XCTAssertEqual(tail.bytesRead, 0)

        append("three\n", to: url)
        XCTAssertTrue(tail.poll())
        XCTAssertEqual(tail.lines, ["one", "two", "three"])
        XCTAssertEqual(tail.bytesRead, 6)  // only the new bytes were read
    }

    func testLogTailHoldsAPartialLineUntilItEnds() {
        let url = tempLog()
        defer { try? FileManager.default.removeItem(at: url) }
        append("one\ntw", to: url)
        var tail = LogTail(url: url, maxLines: 30)
        _ = tail.poll()
        XCTAssertEqual(tail.lines, ["one"])
        append("o\n", to: url)
        _ = tail.poll()
        XCTAssertEqual(tail.lines, ["one", "two"])
    }

    func testLogTailKeepsOnlyTheLastLines() {
        let url = tempLog()
        defer { try? FileManager.default.removeItem(at: url) }
        append((1...50).map { "line \($0)\n" }.joined(), to: url)
        var tail = LogTail(url: url, maxLines: 30)
        _ = tail.poll()
        XCTAssertEqual(tail.lines.count, 30)
        XCTAssertEqual(tail.lines.first, "line 21")
        XCTAssertEqual(tail.lines.last, "line 50")
    }

    func testLogTailStartsNearTheEndOfAHugeFile() {
        let url = tempLog()
        defer { try? FileManager.default.removeItem(at: url) }
        append((1...20000).map { "line \($0)\n" }.joined(), to: url)
        var tail = LogTail(url: url, maxLines: 30)
        _ = tail.poll()
        XCTAssertEqual(tail.lines.last, "line 20000")
        XCTAssertEqual(tail.lines.count, 30)
        XCTAssertLessThanOrEqual(tail.bytesRead, LogTail.initialWindow)
    }

    func testLogTailRestartsWhenTheFileIsReplacedByAShorterOne() {
        let url = tempLog()
        defer { try? FileManager.default.removeItem(at: url) }
        append("old one\nold two\nold three\n", to: url)
        var tail = LogTail(url: url, maxLines: 30)
        _ = tail.poll()
        try! Data("new\n".utf8).write(to: url)
        XCTAssertTrue(tail.poll())
        XCTAssertEqual(tail.lines, ["new"])
    }
}
