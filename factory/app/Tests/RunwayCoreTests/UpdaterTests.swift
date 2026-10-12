import XCTest
@testable import RunwayCore

final class UpdaterTests: XCTestCase {
    func testNoKeyTurnsUpdaterOff() {
        XCTAssertEqual(UpdaterState.decide(publicKey: nil), .off)
        XCTAssertEqual(UpdaterState.decide(publicKey: ""), .off)
        XCTAssertEqual(UpdaterState.decide(publicKey: "  \n"), .off)
    }

    func testKeyTurnsUpdaterOn() {
        XCTAssertEqual(UpdaterState.decide(publicKey: "abc123="), .on)
    }

    func testOffMenuSaysWhy() {
        XCTAssertEqual(UpdaterState.off.menuNote, "Updates off: no signing key")
        XCTAssertNil(UpdaterState.on.menuNote)
    }
}
