import XCTest
@testable import __APP__Core

final class AppLocationTests: XCTestCase {
    let home = "/Users/someone"

    func testApplicationsFoldersAreInstalled() {
        XCTAssertEqual(AppLocation.classify(bundlePath: "/Applications/__APP__.app", home: home), .installed)
        XCTAssertEqual(AppLocation.classify(bundlePath: "/Users/someone/Applications/__APP__.app", home: home), .installed)
    }

    func testDownloadsDesktopAndDiskImagesAreElsewhere() {
        XCTAssertEqual(AppLocation.classify(bundlePath: "/Users/someone/Downloads/__APP__.app", home: home), .elsewhere)
        XCTAssertEqual(AppLocation.classify(bundlePath: "/Volumes/__DISPLAY__/__APP__.app", home: home), .elsewhere)
        let translocated = "/private/var/folders/xy/abc/T/AppTranslocation/1234-5678/d/__APP__.app"
        XCTAssertEqual(AppLocation.classify(bundlePath: translocated, home: home), .elsewhere)
    }

    func testDeveloperBuildsAreNeverAsked() {
        XCTAssertEqual(AppLocation.classify(bundlePath: "/src/__APP__/app/build/__APP__.app", home: home), .development)
        XCTAssertEqual(AppLocation.classify(bundlePath: "/src/__APP__/app/.build/release/__APP__", home: home), .development)
        XCTAssertEqual(AppLocation.classify(
            bundlePath: "/Users/someone/Library/Developer/Xcode/DerivedData/R/Build/Products/Release/__APP__.app",
            home: home), .development)
    }

    func testASubfolderOfApplicationsIsElsewhere() {
        XCTAssertEqual(AppLocation.classify(bundlePath: "/Applications/Tools/__APP__.app", home: home), .elsewhere)
    }
}
