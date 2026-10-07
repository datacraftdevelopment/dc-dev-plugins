import XCTest
@testable import RunwayCore

final class MachineRulesTests: XCTestCase {
    private func json(_ data: Data) -> [String: Any] {
        (try? JSONSerialization.jsonObject(with: data)) as? [String: Any] ?? [:]
    }

    private func tempHome() -> URL {
        let url = FileManager.default.temporaryDirectory.appendingPathComponent("runway-machine-\(UUID().uuidString)")
        addTeardownBlock { try? FileManager.default.removeItem(at: url) }
        return url
    }

    // MARK: decoding

    func testDecodesTheEngineFormat() throws {
        let text = #"""
        {"version": 1,
         "quiet_hours": {"enabled": true, "from": "22:00", "to": "06:00", "days": ["fri", "sat"]},
         "idle_only": {"enabled": true, "minutes": 15},
         "not_on_battery": true, "max_agents": 2, "pause_mode": "stop"}
        """#
        let rules = try MachineFile.decode(Data(text.utf8))
        XCTAssertTrue(rules.quietEnabled)
        XCTAssertEqual(rules.quietFrom, "22:00")
        XCTAssertEqual(rules.quietTo, "06:00")
        XCTAssertEqual(rules.quietDays, ["fri", "sat"])
        XCTAssertTrue(rules.idleEnabled)
        XCTAssertEqual(rules.idleMinutes, 15)
        XCTAssertTrue(rules.notOnBattery)
        XCTAssertEqual(rules.maxAgents, 2)
        XCTAssertEqual(rules.pauseMode, .stop)
    }

    func testEmptyObjectIsDefaults() throws {
        XCTAssertEqual(try MachineFile.decode(Data("{}".utf8)), MachineRules())
    }

    func testDefaultsAreNoRules() {
        let rules = MachineRules()
        XCTAssertFalse(rules.quietEnabled)
        XCTAssertFalse(rules.idleEnabled)
        XCTAssertFalse(rules.notOnBattery)
        XCTAssertEqual(rules.maxAgents, 0)
        XCTAssertEqual(rules.pauseMode, .finish)
        XCTAssertEqual(rules.quietDays, MachineRules.allDays)
        XCTAssertEqual(rules.problems, [])
    }

    func testUnreadableThrows() {
        XCTAssertThrowsError(try MachineFile.decode(Data("not json".utf8)))
        XCTAssertThrowsError(try MachineFile.decode(Data("[1]".utf8)))
    }

    func testLongDayNamesAreNormalised() throws {
        let rules = try MachineFile.decode(Data(#"{"quiet_hours": {"days": ["Monday", "TUE"]}}"#.utf8))
        XCTAssertEqual(rules.quietDays, ["mon", "tue"])
    }

    // MARK: round trip

    func testRoundTrip() throws {
        var rules = MachineRules()
        rules.quietEnabled = true
        rules.quietFrom = "21:30"
        rules.quietTo = "07:15"
        rules.quietDays = ["mon", "wed", "fri"]
        rules.idleEnabled = true
        rules.idleMinutes = 20
        rules.notOnBattery = true
        rules.maxAgents = 3
        rules.pauseMode = .stop
        XCTAssertEqual(try MachineFile.decode(MachineFile.encode(rules, over: nil)), rules)
    }

    func testDefaultsRoundTrip() throws {
        let rules = MachineRules()
        XCTAssertEqual(try MachineFile.decode(MachineFile.encode(rules, over: nil)), rules)
    }

    func testEncodedShapeMatchesTheEngine() throws {
        var rules = MachineRules()
        rules.quietEnabled = true
        rules.maxAgents = 2
        let out = json(MachineFile.encode(rules, over: nil))
        XCTAssertEqual(out["version"] as? Int, 1)
        let quiet = out["quiet_hours"] as? [String: Any]
        XCTAssertEqual(quiet?["enabled"] as? Bool, true)
        XCTAssertEqual(quiet?["from"] as? String, "09:00")
        XCTAssertEqual(quiet?["days"] as? [String], MachineRules.allDays)
        XCTAssertEqual((out["idle_only"] as? [String: Any])?["minutes"] as? Int, 10)
        XCTAssertEqual(out["not_on_battery"] as? Bool, false)
        XCTAssertEqual(out["max_agents"] as? Int, 2)
    }

    func testNoAgentLimitDropsTheKey() throws {
        let existing = Data(#"{"max_agents": 4}"#.utf8)
        let out = json(MachineFile.encode(MachineRules(), over: existing))
        XCTAssertNil(out["max_agents"])
    }

    // MARK: unknown keys

    func testUnknownKeysSurviveASave() throws {
        let existing = Data(#"""
        {"version": 1, "owner": "joe", "extra": {"a": [1, 2]},
         "quiet_hours": {"enabled": false, "from": "09:00", "to": "17:00", "days": ["mon"], "note": "keep me"},
         "idle_only": {"enabled": false, "minutes": 5, "mode": "x"}}
        """#.utf8)
        var rules = try MachineFile.decode(existing)
        rules.quietEnabled = true
        rules.idleMinutes = 30
        let out = json(MachineFile.encode(rules, over: existing))
        XCTAssertEqual(out["owner"] as? String, "joe")
        XCTAssertEqual((out["extra"] as? [String: Any])?["a"] as? [Int], [1, 2])
        let quiet = out["quiet_hours"] as? [String: Any]
        XCTAssertEqual(quiet?["note"] as? String, "keep me")
        XCTAssertEqual(quiet?["enabled"] as? Bool, true)
        let idle = out["idle_only"] as? [String: Any]
        XCTAssertEqual(idle?["mode"] as? String, "x")
        XCTAssertEqual(idle?["minutes"] as? Int, 30)
    }

    func testUnreadableExistingFileIsNotOverwrittenSilently() {
        XCTAssertNil(MachineFile.existingObject(Data("garbage".utf8)))
    }

    // MARK: validation

    func testInvalidTimesAreRejected() {
        for bad in ["", "9:00", "24:00", "12:60", "ab:cd", "09:00:00", "0900", "09:0"] {
            var rules = MachineRules()
            rules.quietEnabled = true
            rules.quietFrom = bad
            XCTAssertFalse(rules.problems.isEmpty, "\(bad) should be rejected")
            XCTAssertTrue(rules.problems.contains { $0.contains("start") }, bad)
        }
        var rules = MachineRules()
        rules.quietEnabled = true
        rules.quietTo = "25:00"
        XCTAssertTrue(rules.problems.contains { $0.contains("end") })
    }

    func testValidTimesPass() {
        for good in ["00:00", "09:05", "23:59"] {
            var rules = MachineRules()
            rules.quietEnabled = true
            rules.quietFrom = good
            rules.quietTo = good
            XCTAssertEqual(rules.problems, [], good)
        }
    }

    func testTimesAreNotCheckedWhileQuietHoursAreOff() {
        var rules = MachineRules()
        rules.quietFrom = "nonsense"
        XCTAssertEqual(rules.problems, [])
    }

    func testSaveRefusesInvalidRules() {
        var rules = MachineRules()
        rules.quietEnabled = true
        rules.quietFrom = "25:00"
        let home = tempHome()
        XCTAssertThrowsError(try MachineStore(home: home).save(rules))
        XCTAssertFalse(FileManager.default.fileExists(atPath: home.appendingPathComponent("machine.json").path))
    }

    func testQuietNeedsADay() {
        var rules = MachineRules()
        rules.quietEnabled = true
        rules.quietDays = []
        XCTAssertFalse(rules.problems.isEmpty)
    }

    func testIdleAndAgentLimits() {
        var rules = MachineRules()
        rules.idleEnabled = true
        rules.idleMinutes = 0
        XCTAssertFalse(rules.problems.isEmpty)
        rules.idleMinutes = 5
        rules.maxAgents = -1
        XCTAssertFalse(rules.problems.isEmpty)
    }

    // MARK: the file

    func testSaveCreatesTheFolderAndLoadsBack() throws {
        let home = tempHome()
        let store = MachineStore(home: home)
        XCTAssertEqual(try store.load(), MachineRules())
        var rules = MachineRules()
        rules.notOnBattery = true
        try store.save(rules)
        XCTAssertTrue(FileManager.default.fileExists(atPath: home.appendingPathComponent("machine.json").path))
        XCTAssertEqual(try store.load(), rules)
        // atomic: no temp files left behind
        XCTAssertEqual(try FileManager.default.contentsOfDirectory(atPath: home.path), ["machine.json"])
    }

    func testSaveKeepsUnknownKeysOnDisk() throws {
        let home = tempHome()
        try FileManager.default.createDirectory(at: home, withIntermediateDirectories: true)
        try Data(#"{"owner": "joe", "max_agents": 1}"#.utf8).write(to: home.appendingPathComponent("machine.json"))
        let store = MachineStore(home: home)
        var rules = try store.load()
        rules.maxAgents = 2
        try store.save(rules)
        let out = json(try Data(contentsOf: home.appendingPathComponent("machine.json")))
        XCTAssertEqual(out["owner"] as? String, "joe")
        XCTAssertEqual(out["max_agents"] as? Int, 2)
    }

    func testUnreadableFileRefusesToBeOverwritten() throws {
        let home = tempHome()
        try FileManager.default.createDirectory(at: home, withIntermediateDirectories: true)
        let url = home.appendingPathComponent("machine.json")
        try Data("{broken".utf8).write(to: url)
        let store = MachineStore(home: home)
        XCTAssertThrowsError(try store.load())
        XCTAssertThrowsError(try store.save(MachineRules()))
        XCTAssertEqual(try String(contentsOf: url, encoding: .utf8), "{broken")
    }

    func testMachineCommand() {
        let tools = RunwayTools(scheduleScript: "/x/schedule.sh", runwayScript: "/x/runway.py")
        XCTAssertEqual(tools.machine(), Command(executable: "/usr/bin/env", arguments: ["python3", "/x/runway.py", "machine"]))
    }
}
