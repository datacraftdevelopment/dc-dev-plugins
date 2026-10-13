import XCTest
@testable import RunwayCore

final class SetupTests: XCTestCase {
    private func stub(_ status: Int32, _ out: String = "", _ err: String = "") -> (Command) async -> CommandResult {
        { _ in CommandResult(status: status, stdout: out, stderr: err) }
    }

    // MARK: this Mac

    func testPythonNeedsThreeNine() async {
        let ok = await SetupChecks.python(run: stub(0, "Python 3.9.6"))
        XCTAssertEqual(ok.status, .ok)
        XCTAssertEqual(ok.detail, "Python 3.9.6")
        let newer = await SetupChecks.python(run: stub(0, "Python 3.13.1"))
        XCTAssertEqual(newer.status, .ok)
        let old = await SetupChecks.python(run: stub(0, "Python 3.8.10"))
        XCTAssertEqual(old.status, .missing)
        XCTAssertTrue(old.detail.contains("3.9"))
    }

    func testPythonReadsStderrAndMissing() async {
        let oldStyle = await SetupChecks.python(run: stub(0, "", "Python 3.10.0"))
        XCTAssertEqual(oldStyle.status, .ok)
        let gone = await SetupChecks.python(run: stub(127, "", "command not found: python3"))
        XCTAssertEqual(gone.status, .missing)
        let junk = await SetupChecks.python(run: stub(0, "hello"))
        XCTAssertEqual(junk.status, .missing)
    }

    func testGit() async {
        let ok = await SetupChecks.git(run: stub(0, "git version 2.45.0"))
        XCTAssertEqual(ok.status, .ok)
        XCTAssertTrue(ok.required)
        let gone = await SetupChecks.git(run: stub(127))
        XCTAssertEqual(gone.status, .missing)
    }

    func testClaudeInstalledOffersSignIn() async {
        let ok = await SetupChecks.claude(run: stub(0, "2.1.0 (Claude Code)"))
        XCTAssertEqual(ok.status, .ok)
        XCTAssertEqual(ok.fix, .signIn)
        let gone = await SetupChecks.claude(run: stub(127))
        XCTAssertEqual(gone.status, .missing)
        XCTAssertNil(gone.fix)
        XCTAssertTrue(gone.required)
    }

    func testHarnessesAreOptional() async {
        let codex = await SetupChecks.codex(run: stub(127))
        XCTAssertEqual(codex.status, .missing)
        XCTAssertFalse(codex.required)
        let cursor = await SetupChecks.cursorAgent(run: stub(0, "1.0"))
        XCTAssertEqual(cursor.status, .ok)
        XCTAssertFalse(cursor.required)
    }

    func testProbeUsesLoginShell() {
        XCTAssertEqual(SetupChecks.probe("claude --version"),
                       Command(executable: "/bin/zsh", arguments: ["-lc", "claude --version"]))
    }

    func testEnginePresentNeedsBothScripts() {
        let present = SetupChecks.engine(checkout: "/co", fileExists: { _ in true })
        XCTAssertEqual(present.status, .ok)
        let half = SetupChecks.engine(checkout: "/co", fileExists: { $0.hasSuffix("runway.py") })
        XCTAssertEqual(half.status, .missing)
        XCTAssertEqual(half.fix, .cloneEngine)
        let none = SetupChecks.engine(checkout: nil, fileExists: { _ in true })
        XCTAssertEqual(none.status, .missing)
        XCTAssertEqual(none.fix, .cloneEngine)
    }

    func testCloneCommand() {
        let c = SetupChecks.cloneCommand(into: "/Users/me/Code")
        XCTAssertEqual(c.arguments, ["git", "clone", "https://github.com/datacraftdevelopment/dc-dev-plugins.git",
                                     "/Users/me/Code/dc-dev-plugins"])
        XCTAssertEqual(SetupChecks.clonedCheckout(into: "/Users/me/Code"), "/Users/me/Code/dc-dev-plugins")
    }

    func testLinearKeyCheckNeverAsksForThePassword() async {
        var seen: Command?
        let present = await SetupChecks.linearKey(run: { seen = $0; return CommandResult(status: 0, stdout: "", stderr: "") })
        XCTAssertEqual(present.status, .ok)
        XCTAssertFalse(seen!.arguments.contains("-w"))
        XCTAssertFalse(seen!.arguments.contains("-g"))
        XCTAssertEqual(seen!.arguments.suffix(2), ["-s", "runway-linear"])
        let missing = await SetupChecks.linearKey(run: stub(44, "", "could not be found"))
        XCTAssertEqual(missing.status, .missing)
        XCTAssertEqual(missing.fix, .saveKey)
    }

    func testGitHubAuthCheck() async {
        var seen: Command?
        let ok = await SetupChecks.githubAuth(run: { seen = $0; return CommandResult(status: 0, stdout: "Logged in", stderr: "") })
        XCTAssertEqual(ok.id, "gh-auth")
        XCTAssertEqual(ok.status, .ok)
        XCTAssertTrue(ok.required)
        XCTAssertEqual(seen, SetupChecks.probe("gh auth status"))
        let out = await SetupChecks.githubAuth(run: stub(1, "", "You are not logged into any GitHub hosts"))
        XCTAssertEqual(out.status, .missing)
        XCTAssertEqual(out.fix, .ghLogin)
        let gone = await SetupChecks.githubAuth(run: stub(127, "", "command not found: gh"))
        XCTAssertEqual(gone.status, .missing)
        XCTAssertNil(gone.fix)
        XCTAssertTrue(gone.detail.contains("gh"))
    }

    func testAllChecksForGitHubUseGhNotTheLinearKey() async {
        let checks = await SetupChecks.all(tracker: .github, checkout: "/co", fileExists: { _ in true }, run: stub(0, "Python 3.12"))
        XCTAssertTrue(checks.contains { $0.id == "gh-auth" })
        XCTAssertFalse(checks.contains { $0.id == "linear-key" })
        let linear = await SetupChecks.all(tracker: .linear, checkout: "/co", fileExists: { _ in true }, run: stub(0, "Python 3.12"))
        XCTAssertFalse(linear.contains { $0.id == "gh-auth" })
    }

    func testGhLoginOpensTerminal() {
        XCTAssertTrue(SetupChecks.ghLoginCommand.arguments.contains { $0.contains("gh auth login") })
    }

    func testAllChecksSkipKeyForGit() async {
        let linear = await SetupChecks.all(tracker: .linear, checkout: "/co", fileExists: { _ in true }, run: stub(0, "Python 3.12"))
        XCTAssertTrue(linear.contains { $0.id == "linear-key" })
        let git = await SetupChecks.all(tracker: .git, checkout: "/co", fileExists: { _ in true }, run: stub(0, "Python 3.12"))
        XCTAssertFalse(git.contains { $0.id == "linear-key" })
        XCTAssertTrue(git.contains { $0.id == "engine" })
    }

    func testBlockingChecks() {
        let checks = [SetupCheck(id: "a", title: "A", status: .ok, detail: "", required: true),
                      SetupCheck(id: "b", title: "B", status: .missing, detail: "", required: false),
                      SetupCheck(id: "c", title: "C", status: .missing, detail: "", required: true)]
        XCTAssertEqual(SetupChecks.blocking(checks).map(\.id), ["c"])
    }

    // MARK: the key

    func testSaveKeyCommandAndMask() async {
        var seen: Command?
        let result = await LinearKey.save("lin_api_SECRET", account: "joe",
                                          run: { seen = $0; return CommandResult(status: 0, stdout: "", stderr: "") })
        XCTAssertTrue(result.succeeded)
        XCTAssertEqual(seen?.executable, "/usr/bin/security")
        XCTAssertEqual(seen?.arguments, ["add-generic-password", "-U", "-s", "runway-linear", "-a", "joe", "-w", "lin_api_SECRET"])
        XCTAssertFalse(LinearKey.displayText(account: "joe").contains("lin_api"))
        XCTAssertTrue(LinearKey.displayText(account: "joe").contains("runway-linear"))
    }

    func testSaveKeyTrimsAndRejectsEmpty() async {
        var ran = false
        let result = await LinearKey.save("  \n ", account: "joe", run: { _ in ran = true; return CommandResult(status: 0, stdout: "", stderr: "") })
        XCTAssertFalse(result.succeeded)
        XCTAssertFalse(ran)
        var arg = ""
        _ = await LinearKey.save(" lin_x \n", account: "joe", run: { arg = $0.arguments.last ?? ""; return CommandResult(status: 0, stdout: "", stderr: "") })
        XCTAssertEqual(arg, "lin_x")
    }

    func testSaveKeyScrubsTheKeyFromFailureOutput() async {
        let result = await LinearKey.save("lin_api_SECRET", account: "joe",
                                          run: stub(1, "", "bad argument lin_api_SECRET"))
        XCTAssertFalse(result.succeeded)
        XCTAssertFalse((result.stdout + result.stderr + result.failureMessage).contains("lin_api_SECRET"))
    }

    func testRedactor() {
        XCTAssertEqual(Redactor.scrub("a SECRET b SECRET", secret: "SECRET"), "a •••• b ••••")
        XCTAssertEqual(Redactor.scrub("nothing", secret: ""), "nothing")
    }

    // MARK: the plan

    private let tools = RunwayTools(checkout: "/co")
    private func config(_ tracker: SetupTracker = .linear, harness: String = "claude") -> SetupConfig {
        SetupConfig(repo: "/r/demo", tracker: tracker, team: "DAT", project: "Runway app", harness: harness, minutes: 15)
    }

    func testLinearPlanRunsTheThreeScriptsInOrder() {
        let steps = SetupPlan.steps(config(), tools: tools)
        XCTAssertEqual(steps.map(\.id), ["setup-repo", "park-authority", "runway-setup", "claims", "install"])
        XCTAssertEqual(steps[0].action, .run(Command(executable: "/bin/bash", arguments: [
            "/co/pm/runway/setup.sh", "/r/demo", "DAT", "Runway app"])))
        XCTAssertEqual(steps[2].action, .run(Command(executable: "/usr/bin/env", arguments: [
            "python3", "/co/pm/runway/runway.py", "--root", "/r/demo", "setup"])))
        XCTAssertEqual(steps[3].action, .claimCheck(Command(executable: "/usr/bin/env", arguments: [
            "python3", "/co/pm/runway/runway.py", "--root", "/r/demo", "status", "--json"])))
        XCTAssertEqual(steps[4].action, .run(Command(executable: "/bin/bash", arguments: [
            "/co/pm/runway/schedule.sh", "install", "/r/demo", "15"])))
    }

    func testGitHubPlanUsesTheSetupScriptsGitHubMode() {
        let steps = SetupPlan.steps(config(.github), tools: tools)
        XCTAssertEqual(steps.map(\.id), ["setup-repo", "park-authority", "runway-setup", "claims", "install"])
        XCTAssertEqual(steps[0].title, "Point the repo at GitHub")
        XCTAssertEqual(steps[0].action, .run(Command(executable: "/bin/bash", arguments: [
            "/co/pm/runway/setup.sh", "/r/demo", "--github"])))
    }

    func testGitHubPlanPassesTheRepoWhenGiven() {
        let cfg = SetupConfig(repo: "/r/demo", tracker: .github, team: "", project: "", harness: "claude", minutes: 15,
                              githubRepo: " acme/widgets ")
        XCTAssertEqual(SetupPlan.steps(cfg, tools: tools)[0].action, .run(Command(executable: "/bin/bash", arguments: [
            "/co/pm/runway/setup.sh", "/r/demo", "--github", "acme/widgets"])))
    }

    func testGitHubValidation() {
        let ok = SetupConfig(repo: "/r", tracker: .github, team: "", project: "", harness: "claude", minutes: 10)
        XCTAssertEqual(SetupPlan.problems(ok), [])
        let bad = SetupConfig(repo: "/r", tracker: .github, team: "", project: "", harness: "claude", minutes: 10, githubRepo: "widgets")
        XCTAssertEqual(SetupPlan.problems(bad), ["The GitHub repo must look like owner/name."])
    }

    func testGitPlanOnlyInstalls() {
        let steps = SetupPlan.steps(config(.git), tools: tools)
        XCTAssertEqual(steps.map(\.id), ["install"])
    }

    func testHarnessStepOnlyWhenNotClaude() {
        XCTAssertFalse(SetupPlan.steps(config(), tools: tools).contains { $0.id == "harness" })
        let steps = SetupPlan.steps(config(harness: "codex"), tools: tools)
        XCTAssertEqual(steps.map(\.id), ["setup-repo", "harness", "park-authority", "runway-setup", "claims", "install"])
        XCTAssertEqual(steps[1].action, .setHarness(repo: "/r/demo", name: "codex"))
    }

    func testDisplayShowsEachCommandQuoted() {
        let steps = SetupPlan.steps(config(), tools: tools)
        XCTAssertEqual(steps[0].display,
                       "bash /co/pm/runway/setup.sh /r/demo DAT 'Runway app'")
        XCTAssertEqual(steps[4].display, "bash /co/pm/runway/schedule.sh install /r/demo 15")
    }

    func testValidation() {
        XCTAssertEqual(SetupPlan.problems(config()), [])
        let bad = SetupConfig(repo: " ", tracker: .linear, team: "", project: "", harness: "claude", minutes: 0)
        XCTAssertEqual(SetupPlan.problems(bad).count, 4)
        let git = SetupConfig(repo: "/r", tracker: .git, team: "", project: "", harness: "claude", minutes: 10)
        XCTAssertEqual(SetupPlan.problems(git), [])
    }

    // MARK: running it

    private final class Recorder: @unchecked Sendable {
        var ran: [Command] = []
        var lines: [String] = []
        var started: [String] = []
    }

    private func runPlan(_ steps: [SetupStep], rec: Recorder,
                         execute: @escaping @Sendable (Command, @Sendable (String) -> Void) async -> CommandResult,
                         harness: @escaping (String, String) throws -> Void = { _, _ in },
                         park: @escaping (String, SetupTracker) throws -> Bool = { _, _ in false }) async -> SetupOutcome {
        await SetupRunner.run(steps,
                              execute: { cmd, out in rec.ran.append(cmd); return await execute(cmd, out) },
                              setHarness: harness,
                              setParkAuthority: park,
                              started: { rec.started.append($0.id) },
                              output: { rec.lines.append($0) })
    }

    func testRunnerRunsEverythingAndStreams() async {
        let rec = Recorder()
        let steps = SetupPlan.steps(config(), tools: tools)
        let outcome = await runPlan(steps, rec: rec) { cmd, out in
            out("ran \(cmd.arguments.count)")
            // the status call returns JSON, which must not be streamed into the sheet
            return CommandResult(status: 0, stdout: cmd.arguments.contains("--json") ? "{\"machine\":\"A\",\"tickets\":[]}" : "", stderr: "")
        }
        XCTAssertEqual(outcome, .completed(warnings: []))
        XCTAssertEqual(rec.started, ["setup-repo", "park-authority", "runway-setup", "claims", "install"])
        XCTAssertEqual(rec.ran.count, 4)
        XCTAssertTrue(rec.lines.contains("$ " + steps[0].display))
        XCTAssertFalse(rec.lines.contains { $0.contains("\"machine\"") })
    }

    func testFailedStepStopsTheFlowAndKeepsItsOutput() async {
        let rec = Recorder()
        let steps = SetupPlan.steps(config(), tools: tools)
        let outcome = await runPlan(steps, rec: rec) { cmd, out in
            if cmd.arguments.contains("setup") {
                out("No Linear API key.")
                return CommandResult(status: 1, stdout: "", stderr: "")
            }
            return CommandResult(status: 0, stdout: "", stderr: "")
        }
        guard case .failed(let step, let output) = outcome else { return XCTFail("expected failure, got \(outcome)") }
        XCTAssertEqual(step.id, "runway-setup")
        XCTAssertTrue(output.contains("No Linear API key."))
        XCTAssertEqual(rec.started, ["setup-repo", "park-authority", "runway-setup"])
        XCTAssertFalse(rec.ran.contains { $0.arguments.contains("install") })
    }

    func testFailureWithOnlyStderrStillShowsIt() async {
        let rec = Recorder()
        let steps = SetupPlan.steps(config(.git), tools: tools)
        let outcome = await runPlan(steps, rec: rec) { _, _ in CommandResult(status: 5, stdout: "", stderr: "launchctl said no") }
        guard case .failed(_, let output) = outcome else { return XCTFail() }
        XCTAssertTrue(output.contains("launchctl said no"))
    }

    func testRerunAfterFailureStartsFromTheTopAndCompletes() async {
        let steps = SetupPlan.steps(config(), tools: tools)
        let first = Recorder()
        let a = await runPlan(steps, rec: first) { cmd, _ in
            if cmd.arguments.contains("setup") { return CommandResult(status: 1, stdout: "", stderr: "nope") }
            return CommandResult(status: 0, stdout: "", stderr: "")
        }
        guard case .failed = a else { return XCTFail() }
        let second = Recorder()
        let b = await runPlan(steps, rec: second) { _, _ in CommandResult(status: 0, stdout: "", stderr: "") }
        XCTAssertEqual(b, .completed(warnings: []))
        XCTAssertEqual(second.started, ["setup-repo", "park-authority", "runway-setup", "claims", "install"])
    }

    func testForeignClaimsWarnButDoNotStop() async {
        let json = """
        {"machine": "Mini-Two", "tickets": [
          {"id": "DAT-5", "title": "Five", "status": "claimed", "claimed_by": "Mini-One"},
          {"id": "DAT-6", "title": "Six", "status": "claimed", "claimed_by": "Mini-Two"}]}
        """
        let rec = Recorder()
        let outcome = await runPlan(SetupPlan.steps(config(), tools: tools), rec: rec) { cmd, _ in
            CommandResult(status: 0, stdout: cmd.arguments.contains("--json") ? json : "", stderr: "")
        }
        XCTAssertEqual(outcome, .completed(warnings: [ForeignClaim(ticket: "DAT-5", title: "Five", machine: "Mini-One")]))
        XCTAssertTrue(rec.ran.contains { $0.arguments.contains("install") })
    }

    func testClaimCheckFailureIsNotFatal() async {
        let rec = Recorder()
        let outcome = await runPlan(SetupPlan.steps(config(), tools: tools), rec: rec) { cmd, _ in
            cmd.arguments.contains("--json") ? CommandResult(status: 1, stdout: "", stderr: "offline") : CommandResult(status: 0, stdout: "", stderr: "")
        }
        XCTAssertEqual(outcome, .completed(warnings: []))
        XCTAssertTrue(rec.lines.contains { $0.contains("couldn't check") })
    }

    func testHarnessEditFailureStopsTheFlow() async {
        struct Boom: LocalizedError { var errorDescription: String? { "no codex profile" } }
        let rec = Recorder()
        let steps = SetupPlan.steps(config(harness: "codex"), tools: tools)
        let outcome = await runPlan(steps, rec: rec, execute: { _, _ in CommandResult(status: 0, stdout: "", stderr: "") },
                                    harness: { _, _ in throw Boom() })
        guard case .failed(let step, let output) = outcome else { return XCTFail() }
        XCTAssertEqual(step.id, "harness")
        XCTAssertTrue(output.contains("no codex profile"))
        XCTAssertFalse(rec.ran.contains { $0.arguments.contains("install") })
    }

    func testForeignClaimParsing() {
        let data = Data("""
        {"machine": "A", "tickets": [
          {"id": "X-1", "title": "t", "status": "claimed", "claimed_by": "B"},
          {"id": "X-2", "title": "t", "status": "ready", "claimed_by": null},
          {"id": "X-3", "title": "t", "status": "claimed", "claimed_by": "A"},
          {"id": "X-4", "title": "t", "status": "resolved", "claimed_by": "B"}]}
        """.utf8)
        XCTAssertEqual(ForeignClaim.parse(data), [ForeignClaim(ticket: "X-1", title: "t", machine: "B")])
        XCTAssertNil(ForeignClaim.parse(Data("nope".utf8)))
    }

    // MARK: harness edit

    func testHarnessEditSetsTheKeyAndKeepsTheRest() throws {
        let dir = FileManager.default.temporaryDirectory.appendingPathComponent("setup-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: dir) }
        let file = dir.appendingPathComponent("runway.json")
        try Data("{\"tracker\": \"linear\", \"harnesses\": {\"codex\": {\"agent_cmd\": \"codex exec\"}}}".utf8).write(to: file)
        try HarnessEdit.set("codex", inRepo: dir.path)
        let json = try JSONSerialization.jsonObject(with: Data(contentsOf: file)) as? [String: Any]
        XCTAssertEqual(json?["harness"] as? String, "codex")
        XCTAssertEqual(json?["tracker"] as? String, "linear")
    }

    func testHarnessEditRefusesAnUnknownProfile() throws {
        let dir = FileManager.default.temporaryDirectory.appendingPathComponent("setup-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: dir) }
        let file = dir.appendingPathComponent("runway.json")
        let original = Data("{\"tracker\": \"linear\"}".utf8)
        try original.write(to: file)
        XCTAssertThrowsError(try HarnessEdit.set("codex", inRepo: dir.path))
        XCTAssertEqual(try Data(contentsOf: file), original)
        XCTAssertThrowsError(try HarnessEdit.set("codex", inRepo: dir.path + "/missing"))
    }

    // MARK: streaming runner

    func testStreamDeliversLinesAndMergesStderr() async {
        final class Box: @unchecked Sendable { var lines: [String] = []; let lock = NSLock()
            func add(_ s: String) { lock.lock(); lines.append(s); lock.unlock() } }
        let box = Box()
        let result = await CommandRunner.stream(
            Command(executable: "/bin/sh", arguments: ["-c", "echo one; echo two >&2; printf three; exit 4"]),
            onLine: { box.add($0) })
        XCTAssertEqual(result.status, 4)
        XCTAssertEqual(Set(box.lines), ["one", "two", "three"])
        XCTAssertEqual(box.lines.count, 3)
    }

    func testSignInOpensTerminalRunningClaude() {
        XCTAssertEqual(SetupChecks.signInCommand.executable, "/usr/bin/osascript")
        XCTAssertTrue(SetupChecks.signInCommand.arguments.contains("tell application \"Terminal\" to do script \"claude\""))
    }

    func testCheckoutOfRunwayScript() {
        XCTAssertEqual(SetupChecks.checkout(ofRunwayScript: "/co/pm/runway/runway.py"), "/co")
        XCTAssertEqual(SetupChecks.checkout(ofRunwayScript: "/co/factory/plugin/runway/runway.py"), "/co")
        XCTAssertEqual(SetupChecks.checkout(ofRunwayScript: "/co/factory/experiments/01-runway/runway.py"), "/co")
    }

    // MARK: a new Mac

    private func registry(_ keys: [String: String]) -> Data {
        let plugins = keys.mapValues { [["scope": "user", "version": $0]] }
        return try! JSONSerialization.data(withJSONObject: ["version": 2, "plugins": plugins])
    }

    func testPmPluginCheck() {
        let ok = SetupChecks.pmPlugin(registry: registry(["pm@dc-dev-plugins": "0.27.2"]))
        XCTAssertEqual(ok.id, "pm")
        XCTAssertEqual(ok.status, .ok)
        XCTAssertTrue(ok.detail.contains("0.27.2"))
        XCTAssertTrue(ok.required)
        let other = SetupChecks.pmPlugin(registry: registry(["pm@someone-else": "1.0"]))
        XCTAssertEqual(other.status, .missing)
        XCTAssertTrue(other.detail.contains("pm@dc-dev-plugins"))
        XCTAssertEqual(SetupChecks.pmPlugin(registry: nil).status, .missing)
    }

    func testMattsSkillsCheck() {
        let ok = SetupChecks.mattSkills(registry: registry(["mattpocock-skills@mattpocock": "1.4.0"]))
        XCTAssertEqual(ok.id, "matt-skills")
        XCTAssertEqual(ok.status, .ok)
        XCTAssertTrue(ok.required)
        let missing = SetupChecks.mattSkills(registry: registry(["pm@dc-dev-plugins": "0.27.2"]))
        XCTAssertEqual(missing.status, .missing)
        XCTAssertTrue(missing.detail.contains("mattpocock-skills"))
        XCTAssertEqual(SetupChecks.mattSkills(registry: Data("junk".utf8)).status, .missing)
    }

    func testRingerIsOptional() async {
        var seen: Command?
        let ok = await SetupChecks.ringer(run: { seen = $0; return CommandResult(status: 0, stdout: "/usr/local/bin/ringer", stderr: "") })
        XCTAssertEqual(ok.id, "ringer")
        XCTAssertEqual(ok.status, .ok)
        XCTAssertFalse(ok.required)
        XCTAssertEqual(seen, SetupChecks.probe("command -v ringer"))
        let gone = await SetupChecks.ringer(run: stub(1))
        XCTAssertEqual(gone.status, .missing)
        XCTAssertFalse(gone.required)
    }

    func testGhRepoAccessCheck() async {
        var seen: Command?
        let ok = await SetupChecks.githubRepoAccess("acme/widgets",
                                                    run: { seen = $0; return CommandResult(status: 0, stdout: "acme/widgets", stderr: "") })
        XCTAssertEqual(ok.id, "gh-repo")
        XCTAssertEqual(ok.status, .ok)
        XCTAssertTrue(ok.required)
        XCTAssertEqual(seen, SetupChecks.probe("gh api repos/acme/widgets --jq .full_name"))
        let denied = await SetupChecks.githubRepoAccess("acme/widgets", run: stub(1, "", "gh: Not Found (HTTP 404)"))
        XCTAssertEqual(denied.status, .missing)
        XCTAssertEqual(denied.fix, .ghLogin)
        XCTAssertTrue(denied.detail.contains("acme/widgets"))
        let gone = await SetupChecks.githubRepoAccess("acme/widgets", run: stub(127, "", "command not found: gh"))
        XCTAssertEqual(gone.status, .missing)
        XCTAssertNil(gone.fix)
        let unknown = await SetupChecks.githubRepoAccess(nil, run: stub(0))
        XCTAssertEqual(unknown.status, .missing)
        XCTAssertTrue(unknown.required)
    }

    func testGhRepoAccessQuotesAnOddName() async {
        var seen: Command?
        _ = await SetupChecks.githubRepoAccess("a/b;rm", run: { seen = $0; return CommandResult(status: 0, stdout: "", stderr: "") })
        XCTAssertEqual(seen, SetupChecks.probe("gh api 'repos/a/b;rm' --jq .full_name"))
    }

    func testGithubRepoFromOrigin() {
        XCTAssertEqual(SetupChecks.githubRepo(fromOrigin: "git@github.com:acme/widgets.git"), "acme/widgets")
        XCTAssertEqual(SetupChecks.githubRepo(fromOrigin: "https://github.com/acme/widgets\n"), "acme/widgets")
        XCTAssertNil(SetupChecks.githubRepo(fromOrigin: "https://gitlab.com/acme/widgets.git"))
        XCTAssertNil(SetupChecks.githubRepo(fromOrigin: ""))
    }

    func testAllChecksForGitHubReadTheRepo() async {
        var lines: [String] = []
        let checks = await SetupChecks.all(tracker: .github, checkout: "/co", fileExists: { _ in true },
                                           repo: "/r/demo", githubRepo: " acme/widgets ",
                                           registry: registry(["pm@dc-dev-plugins": "0.27.2", "mattpocock-skills@mattpocock": "1"]),
                                           run: { cmd in lines.append(cmd.arguments.last ?? ""); return CommandResult(status: 0, stdout: "Python 3.12", stderr: "") })
        XCTAssertTrue(lines.contains("gh api repos/acme/widgets --jq .full_name"))
        for id in ["pm", "matt-skills", "ringer", "codex", "gh-auth", "gh-repo"] {
            XCTAssertTrue(checks.contains { $0.id == id }, id)
        }
        XCTAssertEqual(checks.first { $0.id == "pm" }?.status, .ok)
    }

    func testAllChecksForGitHubFallBackToTheOrigin() async {
        let checks = await SetupChecks.all(tracker: .github, checkout: "/co", fileExists: { _ in true }, repo: "/r/demo",
                                           run: { cmd in
            let line = cmd.arguments.joined(separator: " ")
            if line.contains("remote get-url origin") { return CommandResult(status: 0, stdout: "git@github.com:acme/w.git", stderr: "") }
            if line.contains("gh api") { return CommandResult(status: line.contains("repos/acme/w ") ? 0 : 1, stdout: "", stderr: "") }
            return CommandResult(status: 0, stdout: "x", stderr: "")
        })
        XCTAssertEqual(checks.first { $0.id == "gh-repo" }?.status, .ok)
        let linear = await SetupChecks.all(tracker: .linear, checkout: "/co", fileExists: { _ in true }, run: stub(0, "x"))
        XCTAssertFalse(linear.contains { $0.id == "gh-repo" })
    }

    // MARK: the per-repo keychain item

    private func tempRepo(_ runwayJSON: String?) throws -> URL {
        let dir = FileManager.default.temporaryDirectory.appendingPathComponent("setup-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        addTeardownBlock { try? FileManager.default.removeItem(at: dir) }
        if let runwayJSON { try Data(runwayJSON.utf8).write(to: dir.appendingPathComponent("runway.json")) }
        return dir
    }

    func testKeychainServiceComesFromRunwayJSON() throws {
        let repo = try tempRepo("{\"tracker\": \"linear\", \"linear\": {\"team\": \"DAT\", \"keychain_service\": \"runway-linear-work\"}}")
        XCTAssertEqual(SetupChecks.keychainService(repo: repo.path), "runway-linear-work")
    }

    func testKeychainServiceFallsBack() throws {
        XCTAssertEqual(SetupChecks.keychainService(repo: try tempRepo("{\"linear\": {\"team\": \"DAT\"}}").path), "runway-linear")
        XCTAssertEqual(SetupChecks.keychainService(repo: try tempRepo("{\"linear\": {\"keychain_service\": \" \"}}").path), "runway-linear")
        XCTAssertEqual(SetupChecks.keychainService(repo: try tempRepo("not json").path), "runway-linear")
        XCTAssertEqual(SetupChecks.keychainService(repo: try tempRepo(nil).path), "runway-linear")
        XCTAssertEqual(SetupChecks.keychainService(repo: ""), "runway-linear")
    }

    func testLinearKeyCheckUsesTheRepoService() async {
        var seen: Command?
        let ok = await SetupChecks.linearKey(service: "runway-linear-work",
                                             run: { seen = $0; return CommandResult(status: 0, stdout: "", stderr: "") })
        XCTAssertEqual(seen!.arguments, ["find-generic-password", "-s", "runway-linear-work"])
        XCTAssertTrue(ok.detail.contains("runway-linear-work"))
        let missing = await SetupChecks.linearKey(service: "runway-linear-work", run: stub(44))
        XCTAssertTrue(missing.detail.contains("runway-linear-work"))
    }

    func testAllChecksForLinearUseTheRepoService() async throws {
        let repo = try tempRepo("{\"linear\": {\"keychain_service\": \"runway-linear-work\"}}")
        var seen: [Command] = []
        _ = await SetupChecks.all(tracker: .linear, checkout: "/co", fileExists: { _ in true }, repo: repo.path,
                                  run: { seen.append($0); return CommandResult(status: 0, stdout: "x", stderr: "") })
        XCTAssertTrue(seen.contains { $0.arguments == ["find-generic-password", "-s", "runway-linear-work"] })
    }

    func testSaveKeyUsesTheRepoServiceAndStillMasks() async {
        var seen: Command?
        let result = await LinearKey.save("lin_api_SECRET", service: "runway-linear-work", account: "joe",
                                          run: { seen = $0; return CommandResult(status: 1, stdout: "lin_api_SECRET", stderr: "lin_api_SECRET") })
        XCTAssertEqual(seen?.arguments, ["add-generic-password", "-U", "-s", "runway-linear-work", "-a", "joe", "-w", "lin_api_SECRET"])
        XCTAssertFalse((result.stdout + result.stderr + result.failureMessage).contains("lin_api_SECRET"))
        let shown = LinearKey.displayText(service: "runway-linear-work", account: "joe")
        XCTAssertTrue(shown.contains("runway-linear-work"))
        XCTAssertFalse(shown.contains("lin_api"))
    }

    // MARK: park_authority

    private let owner = "0123456789abcdef0123456789abcdef"

    private func writeOwner(_ repo: URL, _ id: String) throws {
        let pm = repo.appendingPathComponent("_pm")
        try FileManager.default.createDirectory(at: pm, withIntermediateDirectories: true)
        try Data(id.utf8).write(to: pm.appendingPathComponent("park-owner"))
    }

    private func runwayJSON(_ repo: URL) throws -> [String: Any] {
        try JSONSerialization.jsonObject(with: Data(contentsOf: repo.appendingPathComponent("runway.json"))) as! [String: Any]
    }

    func testParkOwnerReadsTheEnginesIdentity() throws {
        let repo = try tempRepo(nil)
        try writeOwner(repo, owner + "\n")
        XCTAssertEqual(try ParkAuthority.owner(repo: repo.path), owner)
    }

    func testParkOwnerIsCreatedLikeTheEngineWhenAbsent() throws {
        let repo = try tempRepo(nil)
        let made = try ParkAuthority.owner(repo: repo.path)
        XCTAssertNotNil(made.range(of: "^[0-9a-f]{32}$", options: .regularExpression))
        XCTAssertEqual(try String(contentsOf: repo.appendingPathComponent("_pm/park-owner"), encoding: .utf8), made)
        XCTAssertEqual(try ParkAuthority.owner(repo: repo.path), made)
    }

    func testParkOwnerRefusesACorruptIdentity() throws {
        let repo = try tempRepo(nil)
        try writeOwner(repo, "not-a-uuid")
        XCTAssertThrowsError(try ParkAuthority.owner(repo: repo.path))
    }

    func testParkAuthorityWrittenWhenAbsentOrEmpty() throws {
        for config in ["{\"tracker\": \"github\", \"github\": {\"park_authority\": \"\", \"repo\": \"acme/w\"}, \"review\": \"panel\"}",
                       "{\"tracker\": \"github\", \"github\": {\"repo\": \"acme/w\"}}",
                       "{\"tracker\": \"github\"}"] {
            let repo = try tempRepo(config)
            try writeOwner(repo, owner)
            XCTAssertTrue(try ParkAuthority.ensure(repo: repo.path, tracker: .github))
            let json = try runwayJSON(repo)
            let gh = json["github"] as? [String: Any]
            XCTAssertEqual(gh?["park_authority"] as? String, owner)
            if config.contains("acme/w") { XCTAssertEqual(gh?["repo"] as? String, "acme/w") }
            XCTAssertEqual(json["tracker"] as? String, "github")
        }
    }

    func testParkAuthorityGoesInTheLinearBlockForLinear() throws {
        let repo = try tempRepo("{\"tracker\": \"linear\", \"linear\": {\"park_authority\": \"\", \"team\": \"DAT\"}}")
        try writeOwner(repo, owner)
        XCTAssertTrue(try ParkAuthority.ensure(repo: repo.path, tracker: .linear))
        let linear = try runwayJSON(repo)["linear"] as? [String: Any]
        XCTAssertEqual(linear?["park_authority"] as? String, owner)
        XCTAssertEqual(linear?["team"] as? String, "DAT")
    }

    func testParkAuthorityAlreadyThisRootLeavesTheFileAlone() throws {
        let repo = try tempRepo("{\"linear\": {\"park_authority\": \"\(owner)\"}}")
        try writeOwner(repo, owner)
        let before = try Data(contentsOf: repo.appendingPathComponent("runway.json"))
        XCTAssertFalse(try ParkAuthority.ensure(repo: repo.path, tracker: .linear))
        XCTAssertEqual(try Data(contentsOf: repo.appendingPathComponent("runway.json")), before)
    }

    func testADifferentOwnerStopsWithoutTouchingTheFile() throws {
        let other = String(repeating: "f", count: 32)
        let repo = try tempRepo("{\"github\": {\"park_authority\": \"\(other)\"}}")
        try writeOwner(repo, owner)
        let before = try Data(contentsOf: repo.appendingPathComponent("runway.json"))
        XCTAssertThrowsError(try ParkAuthority.ensure(repo: repo.path, tracker: .github)) { error in
            XCTAssertTrue(error.localizedDescription.contains("pm/runway/park-ownership.md"))
            XCTAssertTrue(error.localizedDescription.contains(other))
        }
        XCTAssertEqual(try Data(contentsOf: repo.appendingPathComponent("runway.json")), before)
    }

    func testParkAuthorityNeedsARunwayJSON() throws {
        XCTAssertThrowsError(try ParkAuthority.ensure(repo: try tempRepo(nil).path, tracker: .github))
    }

    func testParkAuthorityStepInThePlan() {
        let steps = SetupPlan.steps(config(), tools: tools)
        XCTAssertEqual(steps[1].action, .parkAuthority(repo: "/r/demo", tracker: .linear))
        XCTAssertEqual(SetupPlan.steps(config(.github), tools: tools)[1].action, .parkAuthority(repo: "/r/demo", tracker: .github))
        XCTAssertTrue(steps[1].display.contains("park_authority"))
        XCTAssertFalse(SetupPlan.steps(config(.git), tools: tools).contains { $0.id == "park-authority" })
    }

    func testParkAuthorityWrittenIsCommitted() async {
        let rec = Recorder()
        let outcome = await runPlan(SetupPlan.steps(config(), tools: tools), rec: rec,
                                    execute: { _, _ in CommandResult(status: 0, stdout: "", stderr: "") },
                                    park: { _, _ in true })
        XCTAssertEqual(outcome, .completed(warnings: []))
        XCTAssertTrue(rec.ran.contains(ParkAuthority.addCommand(repo: "/r/demo")))
        XCTAssertTrue(rec.ran.contains(ParkAuthority.commitCommand(repo: "/r/demo")))
        XCTAssertEqual(ParkAuthority.commitCommand(repo: "/r/demo").arguments.suffix(2), ["--", "runway.json"])
    }

    func testParkAuthorityUnchangedMakesNoCommit() async {
        let rec = Recorder()
        _ = await runPlan(SetupPlan.steps(config(), tools: tools), rec: rec,
                          execute: { _, _ in CommandResult(status: 0, stdout: "", stderr: "") },
                          park: { _, _ in false })
        XCTAssertFalse(rec.ran.contains { $0.arguments.contains("commit") })
    }

    func testForeignParkOwnerStopsTheFlow() async {
        struct Foreign: LocalizedError { var errorDescription: String? { "owned elsewhere, see pm/runway/park-ownership.md" } }
        let rec = Recorder()
        let outcome = await runPlan(SetupPlan.steps(config(), tools: tools), rec: rec,
                                    execute: { _, _ in CommandResult(status: 0, stdout: "", stderr: "") },
                                    park: { _, _ in throw Foreign() })
        guard case .failed(let step, let output) = outcome else { return XCTFail() }
        XCTAssertEqual(step.id, "park-authority")
        XCTAssertTrue(output.contains("park-ownership.md"))
        XCTAssertFalse(rec.ran.contains { $0.arguments.contains("install") })
        XCTAssertFalse(rec.ran.contains { $0.arguments.contains("setup") && $0.arguments.contains("--root") })
    }

    func testStreamMissingExecutable() async {
        let result = await CommandRunner.stream(Command(executable: "/nope/nothing", arguments: []), onLine: { _ in })
        XCTAssertFalse(result.succeeded)
        XCTAssertFalse(result.failureMessage.isEmpty)
    }
}
