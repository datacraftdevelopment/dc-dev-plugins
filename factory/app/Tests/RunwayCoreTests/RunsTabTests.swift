import XCTest
@testable import RunwayCore

final class RunsTabTests: XCTestCase {
    private func data(_ lines: [String]) -> Data { Data(lines.joined(separator: "\n").utf8) }

    private let run = #"{"at":"2026-10-07 12:00 CEST","kind":"run","ticket":"DAT-1","attempt":1,"harness":"codex","exit":0,"secs":120,"session_id":"abc","cost_usd":0.5,"num_turns":3,"usage":{"input_tokens":100,"output_tokens":50,"cache_read_input_tokens":999}}"#
    private let failed = #"{"at":"2026-10-07 12:05 CEST","kind":"review","ticket":"DAT-1","attempt":1,"exit":1,"secs":30,"usage":null,"cost_usd":null}"#
    private let outcome = #"{"at":"2026-10-07 12:06 CEST","kind":"outcome","ticket":"DAT-1","attempts":2,"result":"needs-human","detail":""}"#

    func testParsesFieldsNewestFirst() {
        let rows = RunsLog.parse(data([run, failed]))
        XCTAssertEqual(rows.map(\.kind), ["review", "run"])
        let first = rows[1]
        XCTAssertEqual(first.ticket, "DAT-1")
        XCTAssertEqual(first.harness, "codex")
        XCTAssertEqual(first.attempt, 1)
        XCTAssertEqual(first.tokens, 150)  // input + output only
        XCTAssertEqual(first.costUSD, 0.5)
        XCTAssertEqual(first.minutes, 2)
        XCTAssertEqual(first.sessionID, "abc")
    }

    func testResultFromExitAndKind() {
        let rows = RunsLog.parse(data([run, failed, outcome,
            #"{"kind":"outcome","ticket":"T","result":"done"}"#,
            #"{"kind":"finish","ticket":"finish","check_exit":0}"#,
            #"{"kind":"finish","ticket":"finish","check_exit":2}"#,
            #"{"kind":"run","ticket":"T"}"#]))
        XCTAssertEqual(rows.map(\.result), [.unknown, .fail, .pass, .pass, .park, .fail, .pass])
    }

    func testToleratesMissingFieldsAndBadLines() {
        let rows = RunsLog.parse(data(["not json", "", "[1,2]", "{}", #"{"kind":"run","exit":"x","secs":"slow","usage":{}}"#, run]))
        XCTAssertEqual(rows.count, 3)
        XCTAssertEqual(rows[0].ticket, "DAT-1")
        XCTAssertEqual(rows[1].result, .unknown)
        XCTAssertNil(rows[1].secs)
        XCTAssertEqual(rows[1].tokens, 0)
        XCTAssertEqual(rows[2].kind, "")
        XCTAssertEqual(Set(rows.map(\.id)).count, 3)
    }

    func testTotalsMatchRows() {
        let rows = RunsLog.parse(data([run, failed, outcome, run]))
        let totals = RunsLog.totals(rows)
        XCTAssertEqual(totals.rows, 4)
        XCTAssertEqual(totals.tokens, rows.compactMap(\.tokens).reduce(0, +))
        XCTAssertEqual(totals.tokens, 300)
        XCTAssertEqual(totals.costUSD, 1.0, accuracy: 1e-9)
        XCTAssertEqual(totals.minutes, 4.5, accuracy: 1e-9)
    }

    func testTenThousandLinesLoadFast() {
        let big = data(Array(repeating: run, count: 10_000))
        var rows: [RunRecord] = []
        let start = Date()
        rows = RunsLog.parse(big)
        XCTAssertEqual(rows.count, 10_000)
        XCTAssertEqual(RunsLog.totals(rows).tokens, 1_500_000)
        XCTAssertLessThan(Date().timeIntervalSince(start), 2)
    }

    func testTranscriptLookupAcrossProjectFolders() throws {
        let dir = FileManager.default.temporaryDirectory.appendingPathComponent("runs-\(UUID().uuidString)")
        let project = dir.appendingPathComponent("-Users-x-repo")
        try FileManager.default.createDirectory(at: project, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: dir) }
        try Data().write(to: project.appendingPathComponent("abc.jsonl"))
        XCTAssertEqual(RunsLog.transcript(sessionID: "abc", projectsDir: dir)?.lastPathComponent, "abc.jsonl")
        XCTAssertNil(RunsLog.transcript(sessionID: "nope", projectsDir: dir))
        XCTAssertNil(RunsLog.transcript(sessionID: "../abc", projectsDir: dir))
        XCTAssertNil(RunsLog.transcript(sessionID: "abc", projectsDir: dir.appendingPathComponent("missing")))
    }

    func testSnapshotLoadsLogAndPRBodyAndSurvivesNeither() throws {
        let repo = FileManager.default.temporaryDirectory.appendingPathComponent("repo-\(UUID().uuidString)")
        defer { try? FileManager.default.removeItem(at: repo) }
        XCTAssertEqual(RunsSnapshot.load(repo: repo).records.count, 0)
        XCTAssertNil(RunsSnapshot.load(repo: repo).prBody)
        let pm = repo.appendingPathComponent("_pm")
        try FileManager.default.createDirectory(at: pm, withIntermediateDirectories: true)
        try data([run]).write(to: pm.appendingPathComponent("runway-runs.jsonl"))
        try Data("## Summary\n".utf8).write(to: pm.appendingPathComponent("runway-pr.md"))
        let snapshot = RunsSnapshot.load(repo: repo)
        XCTAssertEqual(snapshot.records.count, 1)
        XCTAssertEqual(snapshot.prBody, "## Summary")
    }

    func testRetroCommand() {
        let tools = RunwayTools(scheduleScript: "/s.sh", runwayScript: "/r.py")
        XCTAssertEqual(tools.retro(repo: "/repo").arguments, ["python3", "/r.py", "--root", "/repo", "retro"])
    }
}
