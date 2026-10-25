import XCTest
@testable import __APP__

final class __APP__Tests: XCTestCase {
    func testTheAppHasAVersion() {
        XCTAssertNotNil(Bundle(for: Self.self).bundleIdentifier)
    }
}
