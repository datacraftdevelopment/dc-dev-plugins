import XCTest
@testable import RunwayCore

final class CommandTests: XCTestCase {
    private let tools = RunwayTools(scheduleScript: "/co/factory/experiments/03-linear/schedule.sh",
                                    runwayScript: "/co/factory/experiments/01-runway/runway.py")

    private var chicago: Calendar {
        var cal = Calendar(identifier: .gregorian)
        cal.timeZone = TimeZone(identifier: "America/Chicago")!
        return cal
    }

    func testStart() {
        XCTAssertEqual(tools.start(repo: "/r/demo repo", minutes: 10),
                       Command(executable: "/bin/bash",
                               arguments: ["/co/factory/experiments/03-linear/schedule.sh", "install", "/r/demo repo", "10"]))
    }

    func testStop() {
        XCTAssertEqual(tools.stop(repo: "/r/demo").arguments,
                       ["/co/factory/experiments/03-linear/schedule.sh", "uninstall", "/r/demo"])
    }

    func testRunNowIsLaunchctlKickstart() {
        XCTAssertEqual(RunwayTools.runNow(label: "com.joe.runway.demo", uid: 501),
                       Command(executable: "/bin/launchctl", arguments: ["kickstart", "gui/501/com.joe.runway.demo"]))
    }

    func testPauseChoices() {
        let now = ISO8601DateFormatter().date(from: "2026-10-07T18:00:00Z")!  // 13:00 in Chicago
        XCTAssertEqual(tools.pause(.oneHour, now: now, calendar: chicago).arguments,
                       ["python3", "/co/factory/experiments/01-runway/runway.py", "pause", "--for", "1h"])
        XCTAssertEqual(tools.pause(.untilResumed, now: now, calendar: chicago).arguments,
                       ["python3", "/co/factory/experiments/01-runway/runway.py", "pause"])
        XCTAssertEqual(tools.pause(.untilTomorrow, now: now, calendar: chicago).arguments,
                       ["python3", "/co/factory/experiments/01-runway/runway.py", "pause",
                        "--until", "2026-10-08T08:00:00-05:00"])
    }

    func testResume() {
        XCTAssertEqual(tools.resume(), Command(executable: "/usr/bin/env",
                                               arguments: ["python3", "/co/factory/experiments/01-runway/runway.py", "resume"]))
    }

    func testNextEightAMIsNextOccurrence() {
        let f = ISO8601DateFormatter()
        let evening = f.date(from: "2026-10-07T23:00:00-05:00")!
        XCTAssertEqual(f.string(from: RunwayTools.nextEightAM(after: evening, calendar: chicago)), "2026-10-08T13:00:00Z")
        let early = f.date(from: "2026-10-07T02:00:00-05:00")!
        XCTAssertEqual(f.string(from: RunwayTools.nextEightAM(after: early, calendar: chicago)), "2026-10-07T13:00:00Z")
    }

    func testIsoStringKeepsOffset() {
        let d = ISO8601DateFormatter().date(from: "2026-10-08T13:00:00Z")!
        XCTAssertEqual(RunwayTools.isoLocal(d, calendar: chicago), "2026-10-08T08:00:00-05:00")
    }

    // MARK: runner

    func testRunnerCapturesStderrOnFailure() async {
        let result = await CommandRunner.run(Command(executable: "/bin/sh", arguments: ["-c", "echo boom >&2; exit 3"]))
        XCTAssertEqual(result.status, 3)
        XCTAssertEqual(result.stderr, "boom")
        XCTAssertFalse(result.succeeded)
        XCTAssertEqual(result.failureMessage, "boom")
    }

    func testRunnerSuccess() async {
        let result = await CommandRunner.run(Command(executable: "/bin/sh", arguments: ["-c", "echo hi"]))
        XCTAssertTrue(result.succeeded)
        XCTAssertEqual(result.stdout, "hi")
    }

    func testRunnerMissingExecutable() async {
        let result = await CommandRunner.run(Command(executable: "/nope/nothing", arguments: []))
        XCTAssertFalse(result.succeeded)
        XCTAssertFalse(result.failureMessage.isEmpty)
    }

    func testFailureMessageFallsBackToExitCode() {
        XCTAssertEqual(CommandResult(status: 2, stdout: "", stderr: "").failureMessage, "exited with status 2")
    }

    // MARK: locating the scripts

    func testToolsFromCheckout() {
        XCTAssertEqual(RunwayTools(checkout: "/co"),
                       RunwayTools(scheduleScript: "/co/factory/plugin/runway/schedule.sh",
                                   runwayScript: "/co/factory/plugin/runway/runway.py"))
    }

    func testToolsFromRunwayScriptPath() {
        let t = RunwayTools(runwayScript: "/co/factory/plugin/runway/runway.py")
        XCTAssertEqual(t.scheduleScript, "/co/factory/plugin/runway/schedule.sh")
    }

    func testToolsFromOldLayoutRunwayScriptPath() {
        let t = RunwayTools(runwayScript: "/co/factory/experiments/01-runway/runway.py")
        XCTAssertEqual(t.scheduleScript, "/co/factory/experiments/03-linear/schedule.sh")
    }

    func testLocatePrefersSettingOverPlist() {
        let t = RunwayTools.locate(checkoutSetting: "/mine", projects: [])
        XCTAssertEqual(t?.runwayScript, "/mine/factory/plugin/runway/runway.py")
    }

    func testLocateFallsBackToPlistPath() {
        let p = Project(label: "l", name: "n", repoPath: "/r", tracker: nil, interval: nil, logPath: nil,
                        runwayScript: "/co/factory/experiments/01-runway/runway.py", loaded: true,
                        running: false, lastExit: 0, error: nil)
        XCTAssertEqual(RunwayTools.locate(checkoutSetting: nil, projects: [p])?.scheduleScript,
                       "/co/factory/experiments/03-linear/schedule.sh")
        XCTAssertNil(RunwayTools.locate(checkoutSetting: nil, projects: []))
        XCTAssertNil(RunwayTools.locate(checkoutSetting: "", projects: []))
    }

    func testLabelForRepoMatchesScheduleSh() {
        XCTAssertEqual(ProjectDiscovery.label(forRepo: "/x/demo repo"), "com.joe.runway.demo-repo")
        XCTAssertEqual(ProjectDiscovery.label(forRepo: "/x/dc-dev-plugins"), "com.joe.runway.dc-dev-plugins")
    }

    func testPlistRunwayScriptParsed() throws {
        let url = try XCTUnwrap(Bundle.module.url(forResource: "Fixtures/com.joe.runway.demo.plist", withExtension: nil))
        let job = try LaunchJob.parse(plist: try Data(contentsOf: url))
        XCTAssertEqual(job.runwayScript, "/x/runway.py")
    }
}
