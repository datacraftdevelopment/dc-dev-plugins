import XCTest
@testable import RunwayCore

final class RunwayInfoTests: XCTestCase {
    func testMenuTitleIsRunway() {
        XCTAssertEqual(RunwayInfo.menuTitle, "Runway")
    }

    func testBundleIdentifier() {
        XCTAssertEqual(RunwayInfo.bundleIdentifier, "dev.datacraft.runway")
    }
}
