import XCTest
@testable import RunwayCore

@MainActor
final class ChoresTests: XCTestCase {
    private let sample = """
    {"version":1,"chores":[
      {"id":"codex-refresh","title":"Refresh Codex plugins","why":"w","run":"python3 scripts/refresh_codex.py --install",
       "cwd":"checkout","show_if":"command -v codex","confirm":true},
      {"id":"tracker-setup","title":"Check tracker setup","why":"w","run":"python3 {runway} --root {repo} setup","cwd":"repo"},
      {"id":"broken","title":"No run"},
      {"id":"odd","title":"Odd","run":"x","cwd":"elsewhere"}
    ]}
    """

    func testParseKeepsWellFormedChoresAndSkipsTheRest() {
        let list = ChoreList.parse(Data(sample.utf8))
        XCTAssertEqual(list.chores.map(\.id), ["codex-refresh", "tracker-setup"])
        XCTAssertEqual(list.chores.first?.confirm, true)
        XCTAssertEqual(list.chores.first?.showIf, "command -v codex")
        XCTAssertEqual(list.chores.last?.cwd, .repo)
        XCTAssertEqual(list.chores.last?.confirm, false)
    }

    func testUnknownVersionAndBadJSONAreUnusableNotACrash() {
        guard case .unusable = ChoreList.parse(Data(#"{"version":2,"chores":[]}"#.utf8)) else { return XCTFail() }
        guard case .unusable = ChoreList.parse(Data("not json".utf8)) else { return XCTFail() }
        guard case .unusable = ChoreList.load(checkout: "/nowhere/\(UUID().uuidString)") else { return XCTFail() }
    }

    func testTheRepoChoreRunsInTheRepoWithQuotedPlaceholders() throws {
        let chore = try XCTUnwrap(ChoreList.parse(Data(sample.utf8)).chores.last)
        let spec = try XCTUnwrap(chore.session(runwayScript: "/co/pm/runway/runway.py", checkout: "/co", repo: "/Users/me/Joe's Repo"))
        XCTAssertEqual(spec.executable, "/bin/zsh")
        XCTAssertEqual(spec.arguments, ["-lc", #"python3 '/co/pm/runway/runway.py' --root '/Users/me/Joe'\''s Repo' setup"#])
        XCTAssertEqual(spec.workingDirectory, "/Users/me/Joe's Repo")
        XCTAssertNil(chore.session(runwayScript: "/x", checkout: "/co", repo: nil), "a repo chore needs a repo")
        XCTAssertEqual(chore.sessionKey(repo: "/r"), "chore:tracker-setup:/r")
    }

    func testTheCheckoutChoreRunsInTheCheckoutAndShowIfIsTimeLimited() throws {
        let chore = try XCTUnwrap(ChoreList.parse(Data(sample.utf8)).chores.first)
        XCTAssertEqual(chore.session(runwayScript: "/x", checkout: "/co", repo: nil)?.workingDirectory, "/co")
        XCTAssertEqual(chore.sessionKey(repo: nil), "chore:codex-refresh")
        let check = try XCTUnwrap(chore.showIfCommand(checkout: "/co", repo: nil))
        XCTAssertEqual(check.executable, "/usr/bin/perl")
        XCTAssertEqual(check.arguments, ["-e", "alarm shift; exec @ARGV", "10", "/bin/zsh", "-lc", "cd '/co' && command -v codex"])
        let always = Chore(id: "a", title: "A", why: "", run: "true", cwd: .checkout)
        XCTAssertNil(always.showIfCommand(checkout: "/co", repo: nil))
    }

    func testTheShippedChoresListParses() throws {
        let file = URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()  // factory/app
            .deletingLastPathComponent().deletingLastPathComponent()  // repo root
            .appendingPathComponent("pm/runway/chores.json")
        let data = try XCTUnwrap(FileManager.default.contents(atPath: file.path))
        XCTAssertEqual(ChoreList.parse(data).chores.map(\.id), ["codex-refresh", "retired-plugins", "tracker-setup"])
    }

    func testShowIfReadsExitOneAsNotNeededAndAnyOtherFailureAsStillShown() {
        XCTAssertTrue(Chore.needed(probe: CommandResult(status: 0, stdout: "", stderr: "")))
        XCTAssertFalse(Chore.needed(probe: CommandResult(status: 1, stdout: "", stderr: "")))
        XCTAssertTrue(Chore.needed(probe: CommandResult(status: 127, stdout: "", stderr: "zsh: command not found")))
        XCTAssertTrue(Chore.needed(probe: CommandResult(status: 142, stdout: "", stderr: "")), "the 10 second alarm")
    }

    func testTheResultLineLooksAtTheChoresOwnExitFirst() {
        let chore = Chore(id: "c", title: "Refresh", why: "", run: "x", cwd: .checkout, showIf: "y")
        func probe(_ status: Int32) -> CommandResult { CommandResult(status: status, stdout: "", stderr: "") }
        XCTAssertEqual(chore.result(exit: 2, probe: probe(1)), "Failed (exit 2). Its output is in the Refresh tab.")
        XCTAssertEqual(chore.result(exit: 0, probe: probe(1)), "Done: no longer needed.")
        XCTAssertEqual(chore.result(exit: 0, probe: probe(0)), "Finished, but it still looks needed. Check the output in its tab.")
        XCTAssertTrue(chore.result(exit: nil, probe: probe(1)).hasPrefix("Ended, but Runway couldn't read how"),
                      "no exit status is not a success")
        XCTAssertTrue(chore.result(exit: 0, probe: probe(127)).contains("couldn't check"))
        XCTAssertEqual(chore.result(exit: 0, probe: nil), "Finished. Its output is in the Refresh tab.")
    }
}
