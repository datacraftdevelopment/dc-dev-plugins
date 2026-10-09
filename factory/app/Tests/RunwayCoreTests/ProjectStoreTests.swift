import XCTest
@testable import RunwayCore

@MainActor
final class ProjectStoreTests: XCTestCase {
    private var agents: URL!
    private var repo: URL!
    private var defaults: UserDefaults!
    private var pauseURL: URL!
    private var ran: [Command] = []
    private var nextResult = CommandResult(status: 0, stdout: "", stderr: "")
    private var afterRun: ((Command) -> Void)?

    override func setUp() async throws {
        let base = FileManager.default.temporaryDirectory.appendingPathComponent("runway-store-\(UUID().uuidString)")
        agents = base.appendingPathComponent("LaunchAgents")
        repo = base.appendingPathComponent("demo")
        try FileManager.default.createDirectory(at: agents, withIntermediateDirectories: true)
        try FileManager.default.createDirectory(at: repo.appendingPathComponent("_pm"), withIntermediateDirectories: true)
        pauseURL = base.appendingPathComponent("pause")
        let suite = "runway-test-\(UUID().uuidString)"
        defaults = UserDefaults(suiteName: suite)
        addTeardownBlock { [base] in
            try? FileManager.default.removeItem(at: base)
            UserDefaults().removePersistentDomain(forName: suite)
        }
    }

    private func installPlist() throws {
        let xml = """
        <plist version="1.0"><dict>
          <key>Label</key><string>com.joe.runway.demo</string>
          <key>ProgramArguments</key><array><string>/bin/zsh</string><string>-lc</string>
          <string>cd "\(repo.path)" &amp;&amp; python3 "/co/factory/experiments/01-runway/runway.py" --root "\(repo.path)" loop</string></array>
          <key>StartInterval</key><integer>900</integer>
        </dict></plist>
        """
        try Data(xml.utf8).write(to: agents.appendingPathComponent("com.joe.runway.demo.plist"))
    }

    private func makeStore(loaded: Bool = true, alive: Bool = true) -> ProjectStore {
        let discovery = ProjectDiscovery(launchAgentsDir: agents,
                                         launchctlPrint: { _ in loaded ? "svc = {\n\tstate = waiting\n}" : nil })
        return ProjectStore(discovery: discovery, defaults: defaults, pauseURL: pauseURL,
                            run: { [unowned self] command in
                                self.ran.append(command)
                                self.afterRun?(command)
                                return self.nextResult
                            },
                            pidAlive: { _ in alive })
    }

    func testHideRemovesAProjectUntilShownAgainAndRemembersIt() throws {
        try installPlist()
        let store = makeStore()
        store.refresh()
        XCTAssertEqual(store.entries.map(\.id), ["com.joe.runway.demo"])
        store.hide("com.joe.runway.demo")
        XCTAssertTrue(store.entries.isEmpty)
        XCTAssertEqual(store.hiddenProjects.map(\.label), ["com.joe.runway.demo"])
        XCTAssertTrue(FileManager.default.fileExists(atPath: agents.appendingPathComponent("com.joe.runway.demo.plist").path))
        let reopened = makeStore()
        reopened.refresh()
        XCTAssertTrue(reopened.entries.isEmpty)
        reopened.unhide("com.joe.runway.demo")
        XCTAssertEqual(reopened.entries.map(\.id), ["com.joe.runway.demo"])
        XCTAssertTrue(reopened.hiddenProjects.isEmpty)
    }

    func testStartRunsInstallAndRefreshes() async throws {
        try installPlist()
        let store = makeStore()
        store.refresh()
        let plist = agents.appendingPathComponent("com.joe.runway.demo.plist")
        try FileManager.default.removeItem(at: plist)  // the loop was stopped earlier
        store.refresh()
        let stopped = try XCTUnwrap(store.entries.first)
        XCTAssertEqual(stopped.status.state, .off)
        // schedule.sh install writes the plist; the store must pick it up without being asked
        afterRun = { [self] _ in try? installPlist() }

        await store.startLoop(stopped.project)

        XCTAssertEqual(ran.first?.arguments,
                       ["/co/factory/experiments/03-linear/schedule.sh", "install", repo.path, "15"])
        XCTAssertNil(store.lastError)
        XCTAssertEqual(store.entries.first?.status.state, .idle, "refreshed after the command")
    }

    func testStopRunsUninstallAndKeepsRowToStartAgain() async throws {
        try installPlist()
        let store = makeStore()
        store.refresh()
        let project = try XCTUnwrap(store.projects.first)
        afterRun = { [self] _ in try? FileManager.default.removeItem(at: agents.appendingPathComponent("com.joe.runway.demo.plist")) }

        await store.stopLoop(project)

        XCTAssertEqual(ran.first?.arguments, ["/co/factory/experiments/03-linear/schedule.sh", "uninstall", repo.path])
        XCTAssertEqual(store.entries.count, 1, "stopped loop keeps its row")
        XCTAssertEqual(store.entries.first?.status.state, .off)
        XCTAssertEqual(store.overall, .allOff)
    }

    func testRunNowKickstartsTheLabel() async throws {
        try installPlist()
        let store = makeStore()
        store.refresh()
        await store.runNow(try XCTUnwrap(store.projects.first))
        XCTAssertEqual(ran.first, RunwayTools.runNow(label: "com.joe.runway.demo"))
    }

    func testPauseAndResumeRunRunway() async throws {
        try installPlist()
        let store = makeStore()
        store.refresh()
        await store.pauseAll(.oneHour)
        await store.resume()
        XCTAssertEqual(ran[0].arguments, ["python3", "/co/factory/experiments/01-runway/runway.py", "pause", "--for", "1h"])
        XCTAssertEqual(ran[1].arguments, ["python3", "/co/factory/experiments/01-runway/runway.py", "resume"])
    }

    func testPauseFileDrivesOverallState() async throws {
        try installPlist()
        let store = makeStore()
        store.refresh()
        XCTAssertEqual(store.overall, .running)
        try Data(#"{"until":null,"mode":"finish","at":null}"#.utf8).write(to: pauseURL)
        store.refresh()
        XCTAssertEqual(store.overall, .paused)
        XCTAssertNotNil(store.pause)
    }

    func testFailureShowsStderr() async throws {
        try installPlist()
        let store = makeStore()
        store.refresh()
        nextResult = CommandResult(status: 5, stdout: "", stderr: "Bootstrap failed: 5: Input/output error")
        await store.runNow(try XCTUnwrap(store.projects.first))
        XCTAssertEqual(store.lastError, "Run demo now failed: Bootstrap failed: 5: Input/output error")
        store.dismissError()
        XCTAssertNil(store.lastError)
    }

    func testStaleHeartbeatShowsAsError() throws {
        try installPlist()
        let beat = #"{"version":1,"phase":"agent","ticket":"DAT-14","pid":99999,"since":"2026-10-07T11:00:00Z"}"#
        try Data(beat.utf8).write(to: repo.appendingPathComponent("_pm/runway-state.json"))
        let store = makeStore(alive: false)
        store.refresh()
        guard case .error = store.entries.first?.status.state else {
            return XCTFail("expected error, got \(String(describing: store.entries.first?.status.state))")
        }
        XCTAssertEqual(store.overall, .error)
    }

    func testNoScriptsLocatedReportsInsteadOfRunning() async throws {
        let store = makeStore()
        store.refresh()
        await store.pauseAll(.oneHour)
        XCTAssertTrue(ran.isEmpty)
        XCTAssertNotNil(store.lastError)
    }

    func testCheckoutSettingWinsAndPersists() async throws {
        let store = makeStore()
        store.setCheckout("/mine")
        XCTAssertEqual(store.tools?.runwayScript, "/mine/pm/runway/runway.py")
        XCTAssertEqual(defaults.string(forKey: ProjectStore.checkoutKey), "/mine")
        store.setCheckout(nil)
        XCTAssertNil(store.tools)
    }

    // MARK: notifications

    private func storeWithNotifications(ledger: URL, delivered: @escaping ([NotificationEvent]) -> Void) -> ProjectStore {
        let discovery = ProjectDiscovery(launchAgentsDir: agents, launchctlPrint: { _ in "svc = {\n\tstate = waiting\n}" })
        return ProjectStore(discovery: discovery, defaults: defaults, pauseURL: pauseURL,
                            run: { [unowned self] _ in self.nextResult },
                            pidAlive: { _ in true }, ledgerURL: ledger,
                            machineURL: pauseURL.deletingLastPathComponent().appendingPathComponent("no-machine.json"),
                            deliver: delivered)
    }

    func testRestartDoesNotRepeatANotification() async throws {
        try installPlist()
        nextResult = CommandResult(status: 0, stdout: """
        {"groups":{"waiting":["DAT-1"],"ready_auto":[],"ready_prep":[]},
         "tickets":[{"id":"DAT-1","title":"Pick","status":"needs-human","gate":"human"}]}
        """, stderr: "")
        let ledger = pauseURL.deletingLastPathComponent().appendingPathComponent("support/notified.json")
        var delivered: [NotificationEvent] = []

        let first = storeWithNotifications(ledger: ledger) { delivered += $0 }
        first.refresh()
        for _ in 0..<100 where delivered.isEmpty { try await Task.sleep(nanoseconds: 20_000_000) }
        XCTAssertEqual(delivered.map(\.ticketID), ["DAT-1"])
        first.stop()

        let second = storeWithNotifications(ledger: ledger) { delivered += $0 }
        second.refresh()
        for _ in 0..<15 { try await Task.sleep(nanoseconds: 20_000_000); second.refresh() }
        XCTAssertEqual(delivered.count, 1, "a restart with the saved ledger must not notify again")
        second.stop()
    }
}
