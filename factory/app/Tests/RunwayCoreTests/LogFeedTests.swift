import XCTest
@testable import RunwayCore

final class LogFeedTests: XCTestCase {
    func testParsesTimeKindAndText() {
        let e = LogFeed.entries(["2026-10-07 13:07 EDT  run   DAT-31 Engine: claims  -> runway/x"])
        XCTAssertEqual(e, [LogEntry(time: "13:07", until: nil, kind: "run",
                                    text: "DAT-31 Engine: claims  -> runway/x", count: 1)])
    }

    func testFoldsConsecutiveIdenticalIdleLines() {
        let e = LogFeed.entries([
            "2026-10-08 00:15 EDT  idle  nothing ready without Joe",
            "2026-10-08 00:26 EDT  idle  nothing ready without Joe",
            "2026-10-08 00:36 EDT  idle  nothing ready without Joe",
        ])
        XCTAssertEqual(e, [LogEntry(time: "00:15", until: "00:36", kind: "idle", text: "nothing ready without Joe", count: 3)])
    }

    func testDoesNotFoldAcrossOtherEventsOrDifferentText() {
        let e = LogFeed.entries([
            "2026-10-08 00:15 EDT  idle  nothing ready without Joe",
            "2026-10-08 00:26 EDT  done  DAT-9",
            "2026-10-08 00:36 EDT  idle  nothing ready without Joe",
            "2026-10-08 00:46 EDT  idle  paused",
        ])
        XCTAssertEqual(e.map(\.count), [1, 1, 1, 1])
    }

    func testKeepsContinuationLinesAndSkipsBlanks() {
        let e = LogFeed.entries(["2026-10-07 13:26 EDT  Ready for review: 24 tickets", "  DAT-29   Plugin: docs", "   "])
        XCTAssertEqual(e.count, 2)
        XCTAssertEqual(e[0], LogEntry(time: "13:26", until: nil, kind: "", text: "Ready for review: 24 tickets", count: 1))
        XCTAssertEqual(e[1], LogEntry(time: nil, until: nil, kind: "", text: "DAT-29   Plugin: docs", count: 1))
    }
}
