import XCTest
@testable import RunwayCore

@MainActor
final class ResumeWorkerTests: XCTestCase {
    private let tools = RunwayTools(scheduleScript: "/x/schedule.sh", runwayScript: "/Users/me/My Plugins/runway.py")

    func testResumeCommandIsDiscussWithTheResumeFlagInTheRepo() {
        let spec = tools.discussResumeSession(ticket: "GH 5'x", repo: "/Users/me/Joe's Repo")
        XCTAssertEqual(spec.executable, "/bin/zsh")
        XCTAssertEqual(spec.arguments, ["-lc",
            #"cd '/Users/me/Joe'\''s Repo' && python3 '/Users/me/My Plugins/runway.py' discuss 'GH 5'\''x' --resume"#])
        XCTAssertEqual(spec.workingDirectory, "/Users/me/Joe's Repo")
        let terminal = tools.discussResume(ticket: "GH 5'x", repo: "/Users/me/Joe's Repo")
        XCTAssertEqual(terminal.executable, "/usr/bin/osascript")
        XCTAssertTrue(terminal.arguments.last?.contains("--resume") == true)
    }

    func testAResumeTabIsSeparateFromTheTalkTabForTheSameTicket() {
        let registry = SessionRegistry()
        let talk = registry.open(project: "p", ticket: "GH-7", spec: tools.discussSession(ticket: "GH-7", repo: "/r"))
        let resume = registry.open(project: "p", ticket: "GH-7", resume: true,
                                   spec: tools.discussResumeSession(ticket: "GH-7", repo: "/r"))
        XCTAssertNotEqual(talk.id, resume.id)
        XCTAssertEqual(registry.open(project: "p", ticket: "GH-7", resume: true,
                                     spec: tools.discussResumeSession(ticket: "GH-7", repo: "/r")).id, resume.id)
        XCTAssertEqual(resume.title, "GH-7 (resume)")
    }

    func testStatusParsesResumableAndOnlyShowsTheButtonForResumableTickets() throws {
        let data = Data("""
        {"version":1,"groups":{"waiting":["W","X"],"ready_auto":["E"]},
         "tickets":[{"id":"W","status":"needs-human","resumable":true},
                    {"id":"X","status":"needs-human","resumable":false},
                    {"id":"E","errored":"check-failed","resumable":true}]}
        """.utf8)
        let s = try XCTUnwrap(StatusSnapshot.parse(data))
        XCTAssertTrue(s.canResumeWorker("W"))
        XCTAssertFalse(s.canResumeWorker("X"))
        XCTAssertTrue(s.canResumeWorker("E"))
        XCTAssertFalse(s.canResumeWorker("unknown"))
        let q = try XCTUnwrap(QueueStatus.parse(data))
        XCTAssertEqual(q.tickets.map(\.resumable), [true, false, true])
    }

    func testAnOlderEngineWithoutTheFieldNeverShowsTheButton() throws {
        let data = Data(#"{"version":1,"groups":{"waiting":["W"]},"tickets":[{"id":"W","status":"needs-human"}]}"#.utf8)
        XCTAssertFalse(try XCTUnwrap(StatusSnapshot.parse(data)).canResumeWorker("W"))
        XCTAssertEqual(try XCTUnwrap(QueueStatus.parse(data)).tickets.map(\.resumable), [false])
    }
}
