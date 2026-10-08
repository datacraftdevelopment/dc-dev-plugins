import XCTest
@testable import RunwayCore

final class TicketLinkTests: XCTestCase {
    func testButtonNamesWhatItOpens() {
        XCTAssertEqual(TicketLink.buttonTitle(tracker: "github"), "Open in GitHub")
        XCTAssertEqual(TicketLink.buttonTitle(tracker: "linear"), "Open in Linear")
        XCTAssertEqual(TicketLink.buttonTitle(tracker: "markdown"), "Open in Linear")
        XCTAssertEqual(TicketLink.buttonTitle(tracker: nil), "Open in Linear")
    }
}
