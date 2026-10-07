import XCTest
@testable import RunwayCore

final class RunStateTests: XCTestCase {
    private let now = ISO8601DateFormatter().date(from: "2026-10-07T12:00:00Z")!

    private func project(loaded: Bool = true, running: Bool = false, lastExit: Int? = 0,
                         error: String? = nil, name: String = "demo") -> Project {
        Project(label: "com.joe.runway.\(name)", name: name, repoPath: "/tmp/\(name)", tracker: "markdown",
                interval: 600, logPath: nil, runwayScript: nil, loaded: loaded, running: running,
                lastExit: lastExit, error: error)
    }

    private func beat(phase: String = "check", ticket: String? = "DAT-14", pid: Int = 111,
                      since: String = "2026-10-07T11:54:00Z", reason: String? = nil) -> Heartbeat {
        var json: [String: Any] = ["version": 1, "phase": phase, "pid": pid, "since": since, "attempt": 1]
        if let ticket { json["ticket"] = ticket }
        if let reason { json["reason"] = reason }
        return Heartbeat.parse(try! JSONSerialization.data(withJSONObject: json))!
    }

    private func resolve(_ p: Project, heartbeat: Heartbeat? = nil, pause: PauseInfo? = nil,
                         waiting: Int = 0, alive: Bool = true) -> ProjectStatus {
        StatusResolver.resolve(project: p, heartbeat: heartbeat, pause: pause, waiting: waiting,
                               now: now, pidAlive: { _ in alive })
    }

    // MARK: heartbeat + pause parsing

    func testHeartbeatParse() {
        let hb = beat()
        XCTAssertEqual(hb.phase, "check")
        XCTAssertEqual(hb.ticket, "DAT-14")
        XCTAssertEqual(hb.pid, 111)
        XCTAssertEqual(hb.since, now.addingTimeInterval(-360))
    }

    func testHeartbeatGarbageIsNil() {
        XCTAssertNil(Heartbeat.parse(Data("nope".utf8)))
    }

    func testPauseParse() {
        let p = PauseInfo.parse(Data(#"{"until":"2026-10-07T13:00:00Z","mode":"finish","at":"2026-10-07T12:00:00Z"}"#.utf8))
        XCTAssertEqual(p.until, now.addingTimeInterval(3600))
        XCTAssertEqual(p.mode, "finish")
    }

    func testUnreadablePauseHoldsForever() {
        let p = PauseInfo.parse(Data("garbage".utf8))
        XCTAssertNil(p.until)
        XCTAssertTrue(p.isActive(now: now))
    }

    func testExpiredPauseIsNotActive() {
        let p = PauseInfo(until: now.addingTimeInterval(-1), mode: "finish")
        XCTAssertFalse(p.isActive(now: now))
    }

    func testPauseLoadMissingFileIsNil() {
        let url = FileManager.default.temporaryDirectory.appendingPathComponent("no-pause-\(UUID().uuidString)")
        XCTAssertNil(PauseInfo.load(url, now: now))
    }

    // MARK: per-project state

    func testRunningWithLiveHeartbeat() {
        let s = resolve(project(running: true), heartbeat: beat())
        XCTAssertEqual(s.state, .running)
        XCTAssertEqual(s.detail, "DAT-14 · check · 6m")
    }

    func testStaleHeartbeatIsErrorNotRunning() {
        let s = resolve(project(running: true), heartbeat: beat(), alive: false)
        guard case .error = s.state else { return XCTFail("expected error, got \(s.state)") }
        XCTAssertTrue(s.detail.contains("stale"))
    }

    func testIdleHeartbeatWithDeadPidIsNotError() {
        let s = resolve(project(), heartbeat: beat(phase: "idle", ticket: nil), alive: false)
        XCTAssertEqual(s.state, .idle)
    }

    func testPausedHeartbeatWithDeadPidIsNotError() {
        let s = resolve(project(), heartbeat: beat(phase: "paused", ticket: nil), alive: false)
        XCTAssertEqual(s.state, .idle)
    }

    func testNotLoadedIsOff() {
        XCTAssertEqual(resolve(project(loaded: false)).state, .off)
    }

    func testNotLoadedIgnoresHeartbeat() {
        XCTAssertEqual(resolve(project(loaded: false), heartbeat: beat(), alive: false).state, .off)
    }

    func testProjectErrorWins() {
        let s = resolve(project(error: "Repo not found: /x"))
        XCTAssertEqual(s.state, .error("Repo not found: /x"))
    }

    func testNonzeroExitWhenNotRunningIsError() {
        let s = resolve(project(lastExit: 1))
        XCTAssertEqual(s.state, .error("exit 1"))
    }

    func testNonzeroExitWhileRunningIsFine() {
        let s = resolve(project(running: true, lastExit: 1), heartbeat: beat())
        XCTAssertEqual(s.state, .running)
    }

    func testPauseOverridesRunning() {
        let pause = PauseInfo(until: now.addingTimeInterval(3600), mode: "finish")
        XCTAssertEqual(resolve(project(running: true), heartbeat: beat(), pause: pause).state, .paused)
    }

    func testPausedDetailUntilResumed() {
        let pause = PauseInfo(until: nil, mode: "finish")
        XCTAssertEqual(resolve(project(), pause: pause).detail, "paused until resumed")
    }

    func testDecisionsWaitingWhenIdle() {
        let s = resolve(project(), waiting: 2)
        XCTAssertEqual(s.state, .waiting)
        XCTAssertEqual(s.detail, "2 waiting on you")
    }

    func testRunningBeatsWaitingPerProject() {
        XCTAssertEqual(resolve(project(running: true), heartbeat: beat(), waiting: 1).state, .running)
    }

    func testLoadedWithNothingToShowIsIdle() {
        XCTAssertEqual(resolve(project()).state, .idle)
    }

    func testMachineRuleWaitShowsReason() {
        let s = resolve(project(), heartbeat: beat(phase: "waiting", ticket: nil, reason: "quiet hours"))
        XCTAssertEqual(s.state, .idle)
        XCTAssertEqual(s.detail, "waiting: quiet hours")
    }

    func testAgeFormatting() {
        XCTAssertEqual(StatusResolver.age(from: now.addingTimeInterval(-20), to: now), "20s")
        XCTAssertEqual(StatusResolver.age(from: now.addingTimeInterval(-360), to: now), "6m")
        XCTAssertEqual(StatusResolver.age(from: now.addingTimeInterval(-7200), to: now), "2h")
        XCTAssertEqual(StatusResolver.age(from: now.addingTimeInterval(-172800), to: now), "2d")
    }

    // MARK: overall

    private func status(_ state: RunState, waiting: Int = 0) -> ProjectStatus {
        ProjectStatus(label: "l", name: "n", state: state, detail: "", waiting: waiting)
    }

    func testOverallPriority() {
        let pause = PauseInfo(until: nil, mode: "finish")
        XCTAssertEqual(OverallState.resolve([status(.running), status(.error("x"))], pause: nil, now: now), .error)
        XCTAssertEqual(OverallState.resolve([status(.running)], pause: pause, now: now), .paused)
        XCTAssertEqual(OverallState.resolve([status(.running), status(.waiting, waiting: 1)], pause: nil, now: now), .waiting)
        XCTAssertEqual(OverallState.resolve([status(.running), status(.off)], pause: nil, now: now), .running)
        XCTAssertEqual(OverallState.resolve([status(.idle)], pause: nil, now: now), .running)
        XCTAssertEqual(OverallState.resolve([status(.off), status(.off)], pause: nil, now: now), .allOff)
        XCTAssertEqual(OverallState.resolve([], pause: nil, now: now), .allOff)
    }

    func testOverallPausedButAllOffIsAllOff() {
        let pause = PauseInfo(until: nil, mode: "finish")
        XCTAssertEqual(OverallState.resolve([status(.off)], pause: pause, now: now), .allOff)
    }

    func testBadgeSumsWaiting() {
        XCTAssertEqual(OverallState.badge([status(.waiting, waiting: 2), status(.running, waiting: 1), status(.off)]), 3)
    }

    // MARK: status --json

    func testWaitingCountFromStatusJSON() {
        let json = #"{"version":1,"groups":{"waiting":["DAT-1","DAT-2"],"running":["DAT-3"]},"tickets":[]}"#
        XCTAssertEqual(StatusResolver.waitingCount(statusJSON: Data(json.utf8)), 2)
        XCTAssertNil(StatusResolver.waitingCount(statusJSON: Data("nope".utf8)))
    }
}
