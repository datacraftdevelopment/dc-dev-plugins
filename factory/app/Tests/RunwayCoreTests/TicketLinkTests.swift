import XCTest
@testable import RunwayCore

final class TicketLinkTests: XCTestCase {
    func testButtonNamesWhatItOpens() {
        XCTAssertEqual(TicketLink.buttonTitle(tracker: "github"), "Open in GitHub")
        XCTAssertEqual(TicketLink.buttonTitle(tracker: "linear"), "Open in Linear")
        XCTAssertEqual(TicketLink.buttonTitle(tracker: "markdown"), "Open in Linear")
        XCTAssertEqual(TicketLink.buttonTitle(tracker: nil), "Open in Linear")
    }

    func testNameAndHintsFollowTheTracker() {
        XCTAssertEqual(TicketLink.name(tracker: "github"), "GitHub")
        XCTAssertEqual(TicketLink.name(tracker: "linear"), "Linear")
        XCTAssertEqual(TicketLink.name(tracker: nil), "Linear")
        XCTAssertEqual(TicketLink.openHint(ticket: "GH-16", tracker: "github"), "Open GH-16 in GitHub")
        XCTAssertEqual(TicketLink.openHint(ticket: "ABC-1", tracker: "linear"), "Open ABC-1 in Linear")
        XCTAssertEqual(TicketLink.doubleClickHint(tracker: "github"), "Double-click to open in GitHub.")
        XCTAssertEqual(TicketLink.doubleClickHint(tracker: "linear"), "Double-click to open in Linear.")
    }
}
