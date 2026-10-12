import XCTest
@testable import RunwayCore

/// A scripted `run`: answers by the command's last argument (or a joined line) and records every command it saw.
@MainActor
private final class FakeRunner {
    var answers: [String: CommandResult] = [:]
    private(set) var seen: [Command] = []

    func run(_ command: Command) async -> CommandResult {
        seen.append(command)
        let key = command.arguments.joined(separator: " ")
        for (needle, result) in answers where key.contains(needle) { return result }
        return CommandResult(status: 0, stdout: "", stderr: "")
    }

    static func ok(_ out: String = "") -> CommandResult { CommandResult(status: 0, stdout: out, stderr: "") }
}

final class RunwayUpdateTests: XCTestCase {
    let checkout = "/tmp/dc-dev-plugins"
    var cmds: UpdateCommands { UpdateCommands(checkout: checkout) }

    // MARK: commands

    func testCommandsAreTheOnesTheSpecNames() {
        XCTAssertEqual(cmds.pull, Command(executable: "/usr/bin/env",
                                          arguments: ["git", "-C", checkout, "pull", "--ff-only", "origin", "main"]))
        XCTAssertEqual(cmds.marketplaceUpdate, Command(executable: "/bin/zsh",
                                                       arguments: ["-lc", "claude plugin marketplace update dc-dev-plugins"]))
        XCTAssertEqual(cmds.pluginUpdate, Command(executable: "/bin/zsh",
                                                  arguments: ["-lc", "claude plugin update pm@dc-dev-plugins"]))
        XCTAssertEqual(cmds.fetch.arguments, ["git", "-C", checkout, "fetch", "origin", "main"])
    }

    func testNoCommandStashesResetsSwitchesOrTouchesLaunchctl() {
        let forbidden = ["stash", "reset", "checkout", "switch", "launchctl"]
        for command in cmds.all {
            let words = ([command.executable] + command.arguments)
                .flatMap { $0.split(whereSeparator: { $0 == " " || $0 == "/" }).map(String.init) }
            for word in forbidden {
                XCTAssertFalse(words.contains(word), "\(command) contains \(word)")
            }
            // Every git command names the engine checkout, so no other repo is touched.
            if command.arguments.first == "git" { XCTAssertEqual(Array(command.arguments[1...2]), ["-C", checkout]) }
        }
    }

    // MARK: decisions

    func testDirtyCheckoutSkips() {
        XCTAssertEqual(CheckoutGate.decide(branch: "main", porcelain: " M pm/runway/runway.py"),
                       .skip("uncommitted changes"))
    }

    func testBranchOtherThanMainSkips() {
        XCTAssertEqual(CheckoutGate.decide(branch: "runway/integration", porcelain: ""), .skip("checkout is on a branch"))
        XCTAssertEqual(CheckoutGate.decide(branch: "HEAD", porcelain: ""), .skip("checkout is on a branch"))
    }

    func testCleanMainPulls() {
        XCTAssertEqual(CheckoutGate.decide(branch: "main\n", porcelain: "\n"), .pull)
    }

    func testActiveHeartbeatWaits() {
        let busy = Heartbeat(phase: "agent", ticket: "#9", since: nil, pid: 42, reason: nil, attempt: 1,
                             tickStarted: nil, lastResult: nil)
        let idle = Heartbeat(phase: "idle", ticket: nil, since: nil, pid: nil, reason: nil, attempt: nil,
                             tickStarted: nil, lastResult: nil)
        XCTAssertTrue(RunwayUpdate.midTick([idle, busy], pidAlive: { _ in true }))
        XCTAssertFalse(RunwayUpdate.midTick([idle, nil], pidAlive: { _ in true }))
        // A dead tick isn't mid-tick: waiting on it would wait forever.
        XCTAssertFalse(RunwayUpdate.midTick([busy], pidAlive: { _ in false }))
    }

    @MainActor
    func testRunWaitsWhileATickIsInFlight() async {
        let fake = FakeRunner()
        let outcome = await RunwayUpdate.run(commands: cmds, midTick: true, installedPm: { nil }, run: fake.run)
        XCTAssertEqual(outcome, .waiting)
        XCTAssertTrue(fake.seen.isEmpty)
    }

    @MainActor
    func testRunPullsUpdatesAndReports() async {
        let fake = FakeRunner()
        fake.answers = ["rev-parse --abbrev-ref HEAD": FakeRunner.ok("main"),
                        "rev-parse --short HEAD": FakeRunner.ok("abc1234")]
        let outcome = await RunwayUpdate.run(commands: cmds, midTick: false, installedPm: { "0.27.2" }, run: fake.run)
        XCTAssertEqual(outcome, .done("Updated: engine abc1234, pm 0.27.2. Restart open Claude sessions to pick up the new skills."))
        let lines = fake.seen.map { $0.arguments.joined(separator: " ") }
        let pull = lines.firstIndex { $0.contains("pull --ff-only") }
        let market = lines.firstIndex { $0.contains("marketplace update") }
        let plugin = lines.firstIndex { $0.contains("plugin update pm@") }
        XCTAssertNotNil(pull)
        XCTAssertLessThan(pull!, market!)
        XCTAssertLessThan(market!, plugin!)
    }

    @MainActor
    func testSkippedPullSaysWhyAndStillUpdatesThePlugin() async {
        let fake = FakeRunner()
        fake.answers = ["rev-parse --abbrev-ref HEAD": FakeRunner.ok("main"),
                        "status --porcelain": FakeRunner.ok("?? scratch.txt"),
                        "rev-parse --short HEAD": FakeRunner.ok("abc1234")]
        let outcome = await RunwayUpdate.run(commands: cmds, midTick: false, installedPm: { "0.27.2" }, run: fake.run)
        XCTAssertEqual(outcome, .done("Engine pull skipped: uncommitted changes. "
            + "Updated: engine abc1234, pm 0.27.2. Restart open Claude sessions to pick up the new skills."))
        XCTAssertFalse(fake.seen.contains { $0.arguments.contains("pull") })
        XCTAssertTrue(fake.seen.contains(cmds.pluginUpdate))
    }

    @MainActor
    func testFailingStepStopsTheRunAndShowsItsOutput() async {
        let fake = FakeRunner()
        fake.answers = ["rev-parse --abbrev-ref HEAD": FakeRunner.ok("main"),
                        "marketplace update": CommandResult(status: 1, stdout: "Updating…", stderr: "network down")]
        let outcome = await RunwayUpdate.run(commands: cmds, midTick: false, installedPm: { nil }, run: fake.run)
        XCTAssertEqual(outcome, .failed(step: "claude plugin marketplace update dc-dev-plugins", output: "Updating…\nnetwork down"))
        XCTAssertFalse(fake.seen.contains(cmds.pluginUpdate))
    }

    @MainActor
    func testFailingPullStopsBeforeThePlugin() async {
        let fake = FakeRunner()
        fake.answers = ["rev-parse --abbrev-ref HEAD": FakeRunner.ok("main"),
                        "pull --ff-only": CommandResult(status: 128, stdout: "", stderr: "fatal: Not possible to fast-forward")]
        let outcome = await RunwayUpdate.run(commands: cmds, midTick: false, installedPm: { nil }, run: fake.run)
        guard case .failed(let step, let output) = outcome else { return XCTFail("\(outcome)") }
        XCTAssertEqual(step, "git pull --ff-only origin main")
        XCTAssertEqual(output, "fatal: Not possible to fast-forward")
        XCTAssertFalse(fake.seen.contains(cmds.marketplaceUpdate))
    }

    // MARK: version-change trigger

    func testRecordedVersionTriggersTheRunOnlyOnce() {
        let defaults = UserDefaults(suiteName: "RunwayUpdateTests-\(UUID().uuidString)")!
        var trigger = LaunchTrigger(defaults: defaults)
        XCTAssertTrue(trigger.isDue(build: "120"))
        trigger.record(build: "120")
        XCTAssertFalse(LaunchTrigger(defaults: defaults).isDue(build: "120"))
        XCTAssertTrue(LaunchTrigger(defaults: defaults).isDue(build: "121"))
        // An older build than the recorded one (a downgrade) doesn't run it, and a dev build with no number never does.
        XCTAssertFalse(LaunchTrigger(defaults: defaults).isDue(build: "119"))
        XCTAssertFalse(LaunchTrigger(defaults: defaults).isDue(build: nil))
    }

    // MARK: parity and Behind

    func testVersionCompare() {
        XCTAssertTrue(DottedVersion.isOlder("0.1.0", than: "0.2.0"))
        XCTAssertTrue(DottedVersion.isOlder("0.9", than: "0.10.0"))
        XCTAssertFalse(DottedVersion.isOlder("1.0.0", than: "1.0"))
        XCTAssertFalse(DottedVersion.isOlder("0.27.2", than: "0.27.2"))
    }

    func testAppOlderThanFeedIsBehind() {
        let behind = Parity(app: "0.1.0", feed: "0.2.0", engineSHA: "abc", engineBranch: "main",
                            commitsBehind: 0, installedPm: "0.27.2", checkoutPm: "0.27.2").behind
        XCTAssertEqual(behind, ["app 0.1.0, latest 0.2.0"])
    }

    func testCheckoutBehindOriginIsBehind() {
        let behind = Parity(app: "0.1.0", feed: "0.1.0", engineSHA: "abc", engineBranch: "main",
                            commitsBehind: 3, installedPm: "0.27.2", checkoutPm: "0.27.2").behind
        XCTAssertEqual(behind, ["engine 3 commits behind origin/main"])
    }

    func testInstalledPmOlderThanCheckoutIsBehind() {
        let behind = Parity(app: "0.1.0", feed: nil, engineSHA: "abc", engineBranch: "main",
                            commitsBehind: nil, installedPm: "0.26.0", checkoutPm: "0.27.2").behind
        XCTAssertEqual(behind, ["pm 0.26.0, checkout has 0.27.2"])
    }

    func testUpToDateOrUnknownIsNotBehind() {
        XCTAssertEqual(Parity(app: "0.1.0", feed: nil, engineSHA: nil, engineBranch: nil,
                              commitsBehind: nil, installedPm: nil, checkoutPm: nil).behind, [])
    }

    func testStatusLine() {
        let parity = Parity(app: "0.1.0", feed: nil, engineSHA: "abc1234", engineBranch: "main",
                            commitsBehind: 0, installedPm: "0.27.2", checkoutPm: "0.27.2")
        XCTAssertEqual(parity.line, "Runway 0.1.0 · engine abc1234 (main) · pm 0.27.2")
        XCTAssertEqual(Parity(app: nil, feed: nil, engineSHA: nil, engineBranch: nil, commitsBehind: nil,
                              installedPm: nil, checkoutPm: nil).line, "Runway dev · engine ? · pm ?")
    }

    func testFetchRunsAtMostHourly() {
        let now = Date()
        XCTAssertTrue(FetchThrottle.isDue(last: nil, now: now))
        XCTAssertFalse(FetchThrottle.isDue(last: now.addingTimeInterval(-59 * 60), now: now))
        XCTAssertTrue(FetchThrottle.isDue(last: now.addingTimeInterval(-61 * 60), now: now))
    }

    func testInstalledPmVersionFromTheRegistry() {
        let json = """
        {"version": 2, "plugins": {"pm@dc-dev-plugins": [
          {"scope": "project", "projectPath": "/x", "version": "0.20.0"},
          {"scope": "user", "version": "0.27.2", "installPath": "/y"}]}}
        """
        XCTAssertEqual(PluginVersions.installedPm(registry: Data(json.utf8)), "0.27.2")
        XCTAssertNil(PluginVersions.installedPm(registry: Data("{}".utf8)))
    }

    func testCheckoutPmVersionFromPluginJSON() {
        XCTAssertEqual(PluginVersions.manifestVersion(Data(#"{"name": "pm", "version": "0.27.2"}"#.utf8)), "0.27.2")
        XCTAssertNil(PluginVersions.manifestVersion(Data("nope".utf8)))
    }

    func testFeedLatestVersionFromAppcast() {
        let xml = """
        <?xml version="1.0"?>
        <rss xmlns:sparkle="http://www.andymatuschak.org/xml-namespaces/sparkle" version="2.0"><channel>
          <item><title>0.2.0</title><sparkle:version>130</sparkle:version>
            <sparkle:shortVersionString>0.2.0</sparkle:shortVersionString></item>
          <item><title>0.1.0</title><sparkle:shortVersionString>0.1.0</sparkle:shortVersionString></item>
        </channel></rss>
        """
        XCTAssertEqual(Appcast.latestVersion(Data(xml.utf8)), "0.2.0")
        XCTAssertNil(Appcast.latestVersion(Data("<rss/>".utf8)))
    }
}
