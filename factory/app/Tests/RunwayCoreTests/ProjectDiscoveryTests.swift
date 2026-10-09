import XCTest
@testable import RunwayCore

final class ProjectDiscoveryTests: XCTestCase {
    private func fixture(_ name: String) throws -> Data {
        let url = try XCTUnwrap(Bundle.module.url(forResource: "Fixtures/\(name)", withExtension: nil))
        return try Data(contentsOf: url)
    }

    private func fixtureText(_ name: String) throws -> String {
        String(decoding: try fixture(name), as: UTF8.self)
    }

    private func tempDir() throws -> URL {
        let dir = FileManager.default.temporaryDirectory.appendingPathComponent("runway-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        addTeardownBlock { try? FileManager.default.removeItem(at: dir) }
        return dir
    }

    // MARK: plist

    func testParsesPlist() throws {
        let job = try LaunchJob.parse(plist: try fixture("com.joe.runway.demo.plist"))
        XCTAssertEqual(job.label, "com.joe.runway.demo")
        XCTAssertEqual(job.repoPath, "/Users/joe/Agentic-Mini/_Sandbox/runway/demo repo")
        XCTAssertEqual(job.interval, 600)
        XCTAssertEqual(job.logPath, "/Users/joe/Agentic-Mini/_Sandbox/runway/demo repo/_pm/launchd.log")
    }

    func testGarbagePlistThrows() {
        XCTAssertThrowsError(try LaunchJob.parse(plist: Data("not a plist".utf8)))
    }

    func testPlistWithoutRootThrows() {
        let xml = "<plist version=\"1.0\"><dict><key>Label</key><string>com.joe.runway.x</string></dict></plist>"
        XCTAssertThrowsError(try LaunchJob.parse(plist: Data(xml.utf8)))
    }

    // MARK: launchctl print

    func testLoaded() throws {
        let s = LaunchState.parse(try fixtureText("print-loaded.txt"))
        XCTAssertTrue(s.loaded)
        XCTAssertFalse(s.running)
        XCTAssertEqual(s.lastExit, 0)
    }

    func testLastExitNonZero() throws {
        let s = LaunchState.parse(try fixtureText("print-failed.txt"))
        XCTAssertTrue(s.loaded)
        XCTAssertEqual(s.lastExit, 78)
    }

    func testRunningNeverExited() throws {
        let s = LaunchState.parse(try fixtureText("print-running.txt"))
        XCTAssertTrue(s.loaded)
        XCTAssertTrue(s.running)
        XCTAssertNil(s.lastExit)
    }

    func testNotLoaded() throws {
        XCTAssertFalse(LaunchState.parse(try fixtureText("print-notloaded.txt")).loaded)
        XCTAssertFalse(LaunchState.parse(nil).loaded)
        XCTAssertFalse(LaunchState.parse("").loaded)
    }

    func testGibberishDoesNotCrash() {
        let s = LaunchState.parse("\u{0}\u{1} last exit code = banana\n = {{{")
        XCTAssertNil(s.lastExit)
    }

    // MARK: runway.json

    func testRunwayConfigLinear() throws {
        let c = RunwayConfig.parse(Data(#"{"tracker":"linear","linear":{"team":"DAT","project":"Runway for Mac"}}"#.utf8))
        XCTAssertEqual(c.tracker, "linear")
        XCTAssertEqual(c.projectName, "Runway for Mac")
    }

    func testRunwayConfigGitHubNameIsTheRepo() {
        let c = RunwayConfig.parse(Data(#"{"tracker":"github","github":{"repo":"acme/widgets"}}"#.utf8))
        XCTAssertEqual(c.tracker, "github")
        XCTAssertEqual(c.projectName, "acme/widgets")
    }

    func testRunwayConfigGitHubWithoutRepoHasNoName() {
        XCTAssertNil(RunwayConfig.parse(Data(#"{"tracker":"github"}"#.utf8)).projectName)
        XCTAssertNil(RunwayConfig.parse(Data(#"{"tracker":"github","github":{"repo":""}}"#.utf8)).projectName)
    }

    func testRunwayConfigDefaults() {
        let c = RunwayConfig.parse(Data("{}".utf8))
        XCTAssertEqual(c.tracker, "markdown")
        XCTAssertNil(c.projectName)
    }

    func testRunwayConfigGarbage() {
        XCTAssertNil(RunwayConfig.parse(Data("nope".utf8)).projectName)
    }

    // MARK: discovery

    private func writePlist(_ agents: URL, label: String, repo: String) throws {
        var text = String(decoding: try fixture("com.joe.runway.demo.plist"), as: UTF8.self)
        text = text.replacingOccurrences(of: "/Users/joe/Agentic-Mini/_Sandbox/runway/demo repo", with: repo)
        text = text.replacingOccurrences(of: "com.joe.runway.demo", with: label)
        try text.write(to: agents.appendingPathComponent("\(label).plist"), atomically: true, encoding: .utf8)
    }

    func testDiscoversProjectsByName() throws {
        let root = try tempDir()
        let agents = root.appendingPathComponent("agents")
        try FileManager.default.createDirectory(at: agents, withIntermediateDirectories: true)
        let repo = root.appendingPathComponent("alpha")
        try FileManager.default.createDirectory(at: repo, withIntermediateDirectories: true)
        try #"{"tracker":"linear","linear":{"project":"Alpha Project"}}"#
            .write(to: repo.appendingPathComponent("runway.json"), atomically: true, encoding: .utf8)
        try writePlist(agents, label: "com.joe.runway.alpha", repo: repo.path)
        try "ignore me".write(to: agents.appendingPathComponent("com.other.thing.plist"), atomically: true, encoding: .utf8)

        let printed = try fixtureText("print-failed.txt")
        let discovery = ProjectDiscovery(launchAgentsDir: agents) { label in
            XCTAssertEqual(label, "com.joe.runway.alpha")
            return printed
        }
        let projects = discovery.discover()
        XCTAssertEqual(projects.count, 1)
        let p = projects[0]
        XCTAssertEqual(p.name, "Alpha Project")
        XCTAssertEqual(p.tracker, "linear")
        XCTAssertEqual(p.interval, 600)
        XCTAssertTrue(p.loaded)
        XCTAssertEqual(p.lastExit, 78)
        XCTAssertNil(p.error)
    }

    func testNameFallsBackToRepoFolder() throws {
        let root = try tempDir()
        let agents = root.appendingPathComponent("agents")
        try FileManager.default.createDirectory(at: agents, withIntermediateDirectories: true)
        let repo = root.appendingPathComponent("beta")
        try FileManager.default.createDirectory(at: repo, withIntermediateDirectories: true)
        try writePlist(agents, label: "com.joe.runway.beta", repo: repo.path)
        let p = ProjectDiscovery(launchAgentsDir: agents) { _ in nil }.discover()[0]
        XCTAssertEqual(p.name, "beta")
        XCTAssertFalse(p.loaded)
        XCTAssertNil(p.error)
    }

    func testMissingRepoIsAnError() throws {
        let root = try tempDir()
        let agents = root.appendingPathComponent("agents")
        try FileManager.default.createDirectory(at: agents, withIntermediateDirectories: true)
        try writePlist(agents, label: "com.joe.runway.gone", repo: root.appendingPathComponent("gone").path)
        let p = ProjectDiscovery(launchAgentsDir: agents) { _ in nil }.discover()[0]
        XCTAssertNotNil(p.error)
        XCTAssertEqual(p.name, "gone")
    }

    func testUnreadablePlistIsAnError() throws {
        let root = try tempDir()
        let agents = root.appendingPathComponent("agents")
        try FileManager.default.createDirectory(at: agents, withIntermediateDirectories: true)
        try "garbage".write(to: agents.appendingPathComponent("com.joe.runway.broken.plist"), atomically: true, encoding: .utf8)
        let projects = ProjectDiscovery(launchAgentsDir: agents) { _ in nil }.discover()
        XCTAssertEqual(projects.count, 1)
        XCTAssertEqual(projects[0].name, "broken")
        XCTAssertNotNil(projects[0].error)
    }

    func testSkipsObserverAndOtherNonLoopJobs() throws {
        let root = try tempDir()
        let agents = root.appendingPathComponent("agents")
        try FileManager.default.createDirectory(at: agents, withIntermediateDirectories: true)
        let repo = root.appendingPathComponent("alpha")
        try FileManager.default.createDirectory(at: repo, withIntermediateDirectories: true)
        try writePlist(agents, label: "com.joe.runway.alpha", repo: repo.path)
        let observer = """
        <plist version="1.0"><dict>
          <key>Label</key><string>com.joe.runway.observer.alpha</string>
          <key>ProgramArguments</key><array>
            <string>/opt/homebrew/bin/python3</string><string>\(repo.path)/factory/scripts/observe.py</string>
            <string>--root</string><string>\(repo.path)</string><string>--interval</string><string>600</string>
          </array>
        </dict></plist>
        """
        try observer.write(to: agents.appendingPathComponent("com.joe.runway.observer.alpha.plist"),
                           atomically: true, encoding: .utf8)
        let projects = ProjectDiscovery(launchAgentsDir: agents) { _ in nil }.discover()
        XCTAssertEqual(projects.map(\.label), ["com.joe.runway.alpha"])
        XCTAssertNil(projects[0].error)
    }

    func testMissingAgentsDirIsEmpty() {
        let nowhere = URL(fileURLWithPath: "/nonexistent-\(UUID().uuidString)")
        XCTAssertEqual(ProjectDiscovery(launchAgentsDir: nowhere) { _ in nil }.discover().count, 0)
    }
}
