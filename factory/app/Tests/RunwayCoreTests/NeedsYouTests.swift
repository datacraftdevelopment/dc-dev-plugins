import XCTest
@testable import RunwayCore

final class NeedsYouTests: XCTestCase {
    private func snapshot(_ json: String) throws -> StatusSnapshot {
        try XCTUnwrap(StatusSnapshot.parse(Data(json.utf8)))
    }

    func testRowsFollowWaitingGroupOrderWithReasonAndRecommendation() throws {
        let s = try snapshot("""
        {"groups":{"waiting":["B-2","A-1"]},
         "tickets":[{"id":"A-1","title":"First","status":"needs-human","gate":"human","waiting_on":"go/no-go on the decision packet",
                     "url":"https://github.com/x/y/issues/1",
                     "packet":"### Options\\n- **A** dark\\n- **B** light (recommended)"},
                    {"id":"B-2","title":"Second","status":"needs-human","gate":"auto","waiting_on":"parked after a failed retry"}]}
        """)
        let rows = NeedsYouRow.rows(from: s)
        XCTAssertEqual(rows.map(\.id), ["B-2", "A-1"])
        XCTAssertEqual(rows[0].reason, "parked after a failed retry")
        XCTAssertNil(rows[0].recommended)
        XCTAssertEqual(rows[1].reason, "go/no-go on the decision packet")
        XCTAssertEqual(rows[1].recommended, "**B** light (recommended)")
        XCTAssertEqual(rows[1].url, URL(string: "https://github.com/x/y/issues/1"))
    }

    func testReasonFieldBeatsWaitingOn() throws {
        let s = try snapshot("""
        {"groups":{"waiting":["A-1"]},
         "tickets":[{"id":"A-1","title":"T","status":"needs-human","gate":"auto","waiting_on":"old","reason":"timed out twice"}]}
        """)
        XCTAssertEqual(NeedsYouRow.rows(from: s).first?.reason, "timed out twice")
    }

    func testNothingWaitingMeansNoRows() throws {
        let s = try snapshot(#"{"groups":{"waiting":[],"ready_auto":["A-1"]},"tickets":[{"id":"A-1","title":"T"}]}"#)
        XCTAssertTrue(NeedsYouRow.rows(from: s).isEmpty)
        XCTAssertTrue(NeedsYouRow.rows(from: nil).isEmpty)
    }
}
