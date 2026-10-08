import XCTest
@testable import RunwayCore

final class NotificationTests: XCTestCase {
    private let now = ISO8601DateFormatter().date(from: "2026-10-07T12:00:00Z")!
    private var calendar: Calendar {
        var c = Calendar(identifier: .gregorian)
        c.timeZone = TimeZone(identifier: "UTC")!
        return c
    }

    private func ticket(_ id: String, status: String = "needs-human", gate: String = "human",
                        title: String = "Do the thing") -> StatusSnapshot.Ticket {
        StatusSnapshot.Ticket(id: id, title: title, status: status, gate: gate)
    }

    private func snapshot(_ tickets: [StatusSnapshot.Ticket] = [], ready: Int = 0, loaded: Bool = true,
                          label: String = "com.joe.runway.demo", name: String = "demo") -> ProjectSnapshot {
        ProjectSnapshot(label: label, name: name, loopOn: loaded,
                        status: StatusSnapshot(tickets: tickets, readyCount: ready))
    }

    private func plan(_ snaps: [ProjectSnapshot], ledger: NotificationLedger = NotificationLedger(),
                      at date: Date? = nil, quiet: QuietHours? = nil) -> (events: [NotificationEvent], ledger: NotificationLedger) {
        NotificationPlanner.plan(snaps, ledger: ledger, now: date ?? now, quiet: quiet, calendar: calendar)
    }

    // MARK: status JSON

    func testParseStatusJSON() {
        let json = """
        {"version":1,"groups":{"waiting":["DAT-1","DAT-2"],"ready_auto":["DAT-3"],"ready_prep":["DAT-4","DAT-5"],
         "running":[],"blocked":["DAT-6"],"done":[]},
         "tickets":[{"id":"DAT-1","title":"A","status":"needs-human","gate":"human"},
                    {"id":"DAT-2","title":"B","status":"needs-human","gate":"auto"}]}
        """
        let s = StatusSnapshot.parse(Data(json.utf8))
        XCTAssertEqual(s?.readyCount, 3)
        XCTAssertEqual(s?.tickets.map(\.id), ["DAT-1", "DAT-2"])
        XCTAssertEqual(s?.tickets.last?.gate, "auto")
    }

    func testParseKeepsHttpsTicketLinks() {
        let json = """
        {"groups":{},"tickets":[{"id":"DAT-1","title":"A","url":"https://linear.app/dc/issue/DAT-1/a"},
                                {"id":"DAT-2","title":"B","url":null},{"id":"DAT-3","title":"C","url":"file:///etc"}]}
        """
        let s = StatusSnapshot.parse(Data(json.utf8))
        XCTAssertEqual(s?.urls, ["DAT-1": URL(string: "https://linear.app/dc/issue/DAT-1/a")!])
    }

    func testParseGarbageIsNil() {
        XCTAssertNil(StatusSnapshot.parse(Data("nope".utf8)))
    }

    // MARK: decisions and parked tickets

    func testDecisionPacketNotifiesOnce() {
        let first = plan([snapshot([ticket("DAT-1")])])
        XCTAssertEqual(first.events.count, 1)
        XCTAssertEqual(first.events[0].kind, .decision)
        XCTAssertEqual(first.events[0].ticketID, "DAT-1")
        XCTAssertTrue(first.events[0].body.contains("DAT-1"))
        XCTAssertTrue(first.events[0].title.contains("demo"))
        let second = plan([snapshot([ticket("DAT-1")])], ledger: first.ledger, at: now.addingTimeInterval(60))
        XCTAssertEqual(second.events, [])
    }

    func testAutoGateWaitingMeansParked() {
        let events = plan([snapshot([ticket("DAT-2", gate: "auto")])]).events
        XCTAssertEqual(events.map(\.kind), [.parked])
    }

    func testAnsweredThenParkedAgainNotifiesAgain() {
        let first = plan([snapshot([ticket("DAT-1")])])
        let cleared = plan([snapshot([])], ledger: first.ledger, at: now.addingTimeInterval(60))
        XCTAssertEqual(cleared.events, [])
        let again = plan([snapshot([ticket("DAT-1")])], ledger: cleared.ledger, at: now.addingTimeInterval(120))
        XCTAssertEqual(again.events.count, 1)
    }

    func testProjectWithoutAnswerKeepsItsLedger() {
        let first = plan([snapshot([ticket("DAT-1")])])
        // The status call failed this round: no snapshot for the project, so nothing is forgotten.
        let missed = plan([ProjectSnapshot(label: "com.joe.runway.demo", name: "demo", loopOn: true, status: nil)],
                          ledger: first.ledger)
        let back = plan([snapshot([ticket("DAT-1")])], ledger: missed.ledger, at: now.addingTimeInterval(60))
        XCTAssertEqual(back.events, [])
    }

    func testDecisionsStillNotifyDuringQuietHours() {
        let quiet = QuietHours(from: "09:00", to: "17:00", days: QuietHours.allDays)
        XCTAssertEqual(plan([snapshot([ticket("DAT-1")])], quiet: quiet).events.count, 1)
    }

    // MARK: ready work while the loop is off

    func testReadyWhileOffNotifiesOncePerProject() {
        let result = plan([snapshot(ready: 2, loaded: false)])
        XCTAssertEqual(result.events.count, 1)
        XCTAssertEqual(result.events[0].kind, .idleReady)
        XCTAssertTrue(result.events[0].body.contains("2"))
    }

    func testReadyWhileLoopOnIsSilent() {
        XCTAssertEqual(plan([snapshot(ready: 2, loaded: true)]).events, [])
    }

    func testIdleRepeatsOnlyAfterFourHours() {
        let first = plan([snapshot(ready: 1, loaded: false)])
        let soon = plan([snapshot(ready: 1, loaded: false)], ledger: first.ledger, at: now.addingTimeInterval(3 * 3600 + 59 * 60))
        XCTAssertEqual(soon.events, [])
        let later = plan([snapshot(ready: 1, loaded: false)], ledger: soon.ledger, at: now.addingTimeInterval(4 * 3600))
        XCTAssertEqual(later.events.count, 1)
    }

    func testIdleNeverDuringQuietHours() {
        let quiet = QuietHours(from: "09:00", to: "17:00", days: QuietHours.allDays)
        let held = plan([snapshot(ready: 1, loaded: false)], quiet: quiet)   // 12:00 UTC is inside
        XCTAssertEqual(held.events, [])
        let after = plan([snapshot(ready: 1, loaded: false)], ledger: held.ledger,
                         at: now.addingTimeInterval(6 * 3600), quiet: quiet)  // 18:00
        XCTAssertEqual(after.events.count, 1)
    }

    func testReadyCountZeroIsSilent() {
        XCTAssertEqual(plan([snapshot(ready: 0, loaded: false)]).events, [])
    }

    // MARK: amber icon

    func testReadyWhileOffFlag() {
        XCTAssertTrue(ProjectSnapshot.readyWhileOff([snapshot(ready: 1, loaded: false)]))
        XCTAssertFalse(ProjectSnapshot.readyWhileOff([snapshot(ready: 1, loaded: true)]))
        XCTAssertFalse(ProjectSnapshot.readyWhileOff([snapshot(ready: 0, loaded: false)]))
    }

    // MARK: quiet hours

    func testQuietHoursSameDayWindow() {
        let q = QuietHours(from: "09:00", to: "17:00", days: QuietHours.allDays)
        XCTAssertTrue(q.contains(now, calendar: calendar))
        XCTAssertFalse(q.contains(now.addingTimeInterval(5 * 3600), calendar: calendar))
        XCTAssertFalse(q.contains(now.addingTimeInterval(-3 * 3600 - 1), calendar: calendar))
    }

    func testQuietHoursOvernightBelongsToStartDay() {
        // 2026-10-07 is a Wednesday. 22:00-06:00 on wed runs into Thursday morning.
        let q = QuietHours(from: "22:00", to: "06:00", days: ["wed"])
        let wedNight = ISO8601DateFormatter().date(from: "2026-10-07T23:00:00Z")!
        let thuMorning = ISO8601DateFormatter().date(from: "2026-10-08T05:00:00Z")!
        let thuNight = ISO8601DateFormatter().date(from: "2026-10-08T23:00:00Z")!
        XCTAssertTrue(q.contains(wedNight, calendar: calendar))
        XCTAssertTrue(q.contains(thuMorning, calendar: calendar))
        XCTAssertFalse(q.contains(thuNight, calendar: calendar))
    }

    func testQuietHoursParse() {
        let json = #"{"version":1,"quiet_hours":{"enabled":true,"from":"09:00","to":"17:00","days":["mon","Tue"]}}"#
        XCTAssertEqual(QuietHours.parse(Data(json.utf8)), .some(QuietHours(from: "09:00", to: "17:00", days: ["mon", "tue"])))
        XCTAssertNil(QuietHours.parse(Data(#"{"quiet_hours":{"enabled":false,"from":"09:00","to":"17:00"}}"#.utf8)))
        XCTAssertNil(QuietHours.parse(Data(#"{}"#.utf8)))
    }

    // MARK: ledger persistence (restart)

    func testLedgerSurvivesRestart() throws {
        let url = FileManager.default.temporaryDirectory
            .appendingPathComponent("runway-ledger-\(UUID().uuidString)/notified.json")
        defer { try? FileManager.default.removeItem(at: url.deletingLastPathComponent()) }

        let firstRun = plan([snapshot([ticket("DAT-1")], ready: 1, loaded: true), snapshot(ready: 3, loaded: false, label: "b", name: "b")])
        XCTAssertEqual(firstRun.events.count, 2)
        try firstRun.ledger.save(to: url)

        let restarted = NotificationLedger.load(from: url)
        let again = plan([snapshot([ticket("DAT-1")]), snapshot(ready: 3, loaded: false, label: "b", name: "b")],
                         ledger: restarted, at: now.addingTimeInterval(600))
        XCTAssertEqual(again.events, [])
    }

    func testMissingOrCorruptLedgerIsEmpty() throws {
        let dir = FileManager.default.temporaryDirectory.appendingPathComponent("runway-ledger-\(UUID().uuidString)")
        defer { try? FileManager.default.removeItem(at: dir) }
        let url = dir.appendingPathComponent("notified.json")
        XCTAssertEqual(NotificationLedger.load(from: url), NotificationLedger())
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        try Data("garbage".utf8).write(to: url)
        XCTAssertEqual(NotificationLedger.load(from: url), NotificationLedger())
    }

    // MARK: routing

    func testRouteRoundTrip() {
        let events = plan([snapshot([ticket("DAT-1")]), snapshot(ready: 1, loaded: false, label: "b", name: "b")]).events
        for event in events {
            XCTAssertEqual(NotificationRoute(userInfo: event.userInfo), event.route)
        }
        XCTAssertEqual(events.first(where: { $0.kind == .decision })?.route.tab, .decisions)
        XCTAssertEqual(events.first(where: { $0.kind == .idleReady })?.route.tab, .projects)
    }
}
