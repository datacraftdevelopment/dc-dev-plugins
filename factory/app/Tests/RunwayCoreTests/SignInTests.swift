import XCTest
@testable import RunwayCore

@MainActor
final class SignInTests: XCTestCase {
    private let tools = RunwayTools(scheduleScript: "/co/pm/runway/schedule.sh", runwayScript: "/co/pm/runway/runway.py")

    private func snapshot(_ signin: String) throws -> StatusSnapshot {
        try XCTUnwrap(StatusSnapshot.parse(Data(#"{"version":1,"groups":{},"tickets":[],"signin":\#(signin)}"#.utf8)))
    }

    private let claudeOut = #"{"at":"x","ok":false,"checks":[{"name":"claude","label":"Claude Code","fix":"claude auth login","ok":false,"detail":"Claude Code needs signing in (`claude auth login`)"},{"name":"gh","label":"GitHub CLI","fix":"gh auth login","ok":true,"detail":"GitHub CLI signed in"}]}"#

    func testAFailingCheckIsANeedWithItsFix() throws {
        let needs = SignInNeed.resolve([try snapshot(claudeOut)], pause: nil)
        XCTAssertEqual(needs, [SignInNeed(id: "claude", label: "Claude Code", fix: "claude auth login",
                                          detail: "Claude Code needs signing in (`claude auth login`)")])
    }

    func testTheSameToolFailingInTwoProjectsIsOneNeed() throws {
        XCTAssertEqual(SignInNeed.resolve([try snapshot(claudeOut), try snapshot(claudeOut)], pause: nil).map(\.id), ["claude"])
    }

    func testPassingChecksAndNoSigninAreNoNeeds() throws {
        let ok = #"{"ok":true,"checks":[{"name":"claude","label":"Claude Code","fix":"claude auth login","ok":true,"detail":"ok"}]}"#
        XCTAssertTrue(SignInNeed.resolve([try snapshot(ok), try snapshot("null")], pause: nil).isEmpty)
    }

    func testASignInPauseIsANeedButAHandSetPauseIsNot() throws {
        let signedOut = PauseInfo.parse(Data(#"{"until":null,"mode":"finish","reason":"signed-out"}"#.utf8))
        XCTAssertEqual(signedOut.reason, "signed-out")
        let needs = SignInNeed.resolve([], pause: signedOut)
        XCTAssertEqual(needs.map(\.id), ["claude"])
        XCTAssertEqual(needs.first?.fix, "claude auth login")
        let handSet = PauseInfo.parse(Data(#"{"until":null,"mode":"finish"}"#.utf8))
        XCTAssertNil(handSet.reason)
        XCTAssertTrue(SignInNeed.resolve([], pause: handSet).isEmpty)
    }

    func testAnOlderEngineWithoutLabelOrFixStillShowsTheNeedWithoutAButtonCommand() throws {
        let old = #"{"ok":false,"checks":[{"name":"linear","ok":false,"detail":"Linear key missing"}]}"#
        let need = try XCTUnwrap(SignInNeed.resolve([try snapshot(old)], pause: nil).first)
        XCTAssertEqual(need.label, "Linear")
        XCTAssertNil(need.fix)
        XCTAssertNil(need.session())
    }

    func testTheFixRunsThroughALoginShellInHome() throws {
        let need = try XCTUnwrap(SignInNeed.resolve([try snapshot(claudeOut)], pause: nil).first)
        XCTAssertEqual(need.session(home: "/Users/me"),
                       LaunchSpec(executable: "/bin/zsh", arguments: ["-lc", "claude auth login"], workingDirectory: "/Users/me"))
    }

    func testFollowUpResumesOnlyWhenEveryCheckPassed() {
        XCTAssertEqual(SignInFollowUp.commands(allPassed: false, tools: tools, waitingLoops: ["com.joe.runway.demo"]), [])
        let commands = SignInFollowUp.commands(allPassed: true, tools: tools, waitingLoops: ["com.joe.runway.demo"])
        XCTAssertEqual(commands.first?.arguments, ["python3", "/co/pm/runway/runway.py", "resume", "--if-reason", "signed-out"])
        XCTAssertEqual(commands.last, RunwayTools.runNow(label: "com.joe.runway.demo"))
        XCTAssertEqual(tools.signin(repo: "/r").arguments, ["python3", "/co/pm/runway/runway.py", "--root", "/r", "signin", "--json"])
    }

    func testOnlyLoopsWaitingOnASignInGetATick() {
        func beat(_ phase: String, _ reason: String? = nil) -> Heartbeat {
            Heartbeat(phase: phase, ticket: nil, since: nil, pid: nil, reason: reason, attempt: nil, tickStarted: nil, lastResult: nil)
        }
        XCTAssertTrue(SignInFollowUp.wasWaiting(beat("waiting", "Claude Code needs signing in (`claude auth login`)"), pauseReason: nil))
        XCTAssertTrue(SignInFollowUp.wasWaiting(beat("paused"), pauseReason: "signed-out"))
        XCTAssertFalse(SignInFollowUp.wasWaiting(beat("paused"), pauseReason: nil), "a pause Joe set stays paused")
        XCTAssertFalse(SignInFollowUp.wasWaiting(beat("waiting", "quiet hours until 17:00"), pauseReason: nil))
        XCTAssertFalse(SignInFollowUp.wasWaiting(beat("idle"), pauseReason: "signed-out"))
        XCTAssertFalse(SignInFollowUp.wasWaiting(nil, pauseReason: "signed-out"))
    }

    func testACommandSessionIsOneTabPerKeyAndReportsItsExitOnce() {
        let registry = SessionRegistry()
        var exited: [String] = []
        registry.onExit = { exited.append($0.command?.key ?? "") }
        let spec = LaunchSpec(executable: "/bin/zsh", arguments: ["-lc", "claude auth login"], workingDirectory: "/h")
        let command = CommandSession(key: "signin:claude", title: "Sign in: Claude Code", line: "claude auth login")
        let first = registry.open(command: command, spec: spec)
        XCTAssertEqual(registry.open(command: command, spec: spec).id, first.id)
        XCTAssertEqual(first.title, "Sign in: Claude Code")
        registry.markExited(first.id, exitCode: 3)
        registry.markExited(first.id, exitCode: 0)
        XCTAssertEqual(exited, ["signin:claude"])
        XCTAssertEqual(registry.sessions.first?.exitCode, 3, "the first exit is the one kept")
        XCTAssertNotEqual(registry.open(command: command, spec: spec).id, first.id, "a finished tab doesn't take a new run")
    }

    func testPopOutOfASignInRunsItsLineInTerminal() {
        let command = RunwayTools.terminal(line: #"claude auth login"#)
        XCTAssertEqual(command.executable, "/usr/bin/osascript")
        XCTAssertEqual(command.arguments.last, #"tell application "Terminal" to do script "claude auth login""#)
    }
}
