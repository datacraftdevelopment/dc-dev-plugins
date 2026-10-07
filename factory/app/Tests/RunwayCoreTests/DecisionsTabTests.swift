import XCTest
@testable import RunwayCore

final class DecisionsTabTests: XCTestCase {
    private func fixture() -> Data {
        try! Data(contentsOf: Bundle.module.url(forResource: "status", withExtension: "json", subdirectory: "Fixtures")!)
    }

    private let tools = RunwayTools(scheduleScript: "/co/s.sh", runwayScript: "/co/runway.py")
    private let statusCommand = Command(executable: "/usr/bin/status", arguments: [])
    private let answerCommand = Command(executable: "/usr/bin/answer", arguments: [])

    // MARK: command

    func testGoRunsTheExactCommand() {
        XCTAssertEqual(tools.answer(go: true, ticket: "DAT-30", note: "ship it", repo: "/r"),
                       Command(executable: "/usr/bin/env",
                               arguments: ["python3", "/co/runway.py", "--root", "/r", "go", "DAT-30", "ship it"]))
    }

    func testNoRunsTheExactCommandAndKeepsAnEmptyNote() {
        XCTAssertEqual(tools.answer(go: false, ticket: "DAT-30", note: "", repo: "/r").arguments,
                       ["python3", "/co/runway.py", "--root", "/r", "no", "DAT-30", ""])
    }

    func testNoteIsOneArgumentWhateverItHolds() {
        let note = "say \"hi\"; rm -rf /\nline two"
        XCTAssertEqual(tools.answer(go: true, ticket: "DAT-30", note: note, repo: "/r").arguments.last, note)
    }

    func testNoteStartingWithADashIsNotTakenForAnOption() {
        XCTAssertEqual(tools.answer(go: true, ticket: "DAT-30", note: "-x", repo: "/r").arguments.suffix(3),
                       ["DAT-30", "--", "-x"])
    }

    // MARK: decoding

    func testDecisionsAreTheWaitingTicketsWithTheirPacket() throws {
        let queue = try XCTUnwrap(QueueStatus.parse(fixture()))
        XCTAssertEqual(queue.decisions.map(\.id), ["DAT-30"], "ready_prep tickets aren't waiting on an answer")
        XCTAssertTrue(try XCTUnwrap(queue.decisions[0].packet).hasPrefix("### Decision needed"))
        XCTAssertNil(queue.tickets.first { $0.id == "DAT-22" }?.packet)
    }

    // MARK: markdown

    func testPacketBlocks() {
        let blocks = PacketMarkdown.blocks("""
        ### Decision needed
        Go or no?
        still the same paragraph

        ### Options
        - **A** one
        * B two (recommended)
        1. first
        2) second
        ```
        code line
        ```
        """)
        XCTAssertEqual(blocks, [
            .heading(level: 3, text: "Decision needed"),
            .paragraph("Go or no? still the same paragraph"),
            .heading(level: 3, text: "Options"),
            .bullet("**A** one"),
            .bullet("B two (recommended)"),
            .numbered(number: 1, text: "first"),
            .numbered(number: 2, text: "second"),
            .code("code line"),
        ])
    }

    func testRecommendedLineIsMarked() {
        XCTAssertTrue(PacketMarkdown.isRecommended("B light (recommended)"))
        XCTAssertTrue(PacketMarkdown.isRecommended("**Recommendation:** B"))
        XCTAssertFalse(PacketMarkdown.isRecommended("A dark"))
    }

    // MARK: answering

    @MainActor private func feed(answer: CommandResult, calls: Calls) -> DecisionsFeed {
        let status = String(decoding: fixture(), as: UTF8.self)
        let statusCommand = self.statusCommand
        return DecisionsFeed(run: { command in
            await calls.record(command)
            return command == statusCommand ? CommandResult(status: 0, stdout: status, stderr: "") : answer
        })
    }

    @MainActor func testRefreshNeverAnswersAnything() async {
        let calls = Calls()
        let feed = feed(answer: CommandResult(status: 0, stdout: "", stderr: ""), calls: calls)
        await feed.refresh(statusCommand)
        await feed.refresh(statusCommand)
        let ran = await calls.commands
        XCTAssertEqual(ran, [statusCommand, statusCommand])
        XCTAssertTrue(feed.answers.isEmpty)
        XCTAssertEqual(feed.queue?.decisions.map(\.id), ["DAT-30"])
    }

    @MainActor func testGoRunsTheCommandThenRefreshesAndRecordsTheAnswer() async throws {
        let calls = Calls()
        let feed = feed(answer: CommandResult(status: 0, stdout: "approved", stderr: ""), calls: calls)
        await feed.refresh(statusCommand)
        let ticket = try XCTUnwrap(feed.queue?.decisions.first)
        await feed.answer(ticket, go: true, note: "B please", command: answerCommand, status: statusCommand)
        let ran = await calls.commands
        XCTAssertEqual(ran, [statusCommand, answerCommand, statusCommand], "answer once, then refresh")
        XCTAssertEqual(feed.answers["DAT-30"]?.text, "Answered: go “B please”, picked up on the next tick")
        XCTAssertNil(feed.errors["DAT-30"])
        XCTAssertFalse(feed.isAnswering("DAT-30"))
    }

    @MainActor func testNoWithoutANoteReadsPlainly() async throws {
        let calls = Calls()
        let feed = feed(answer: CommandResult(status: 0, stdout: "", stderr: ""), calls: calls)
        await feed.refresh(statusCommand)
        let ticket = try XCTUnwrap(feed.queue?.decisions.first)
        await feed.answer(ticket, go: false, note: "  ", command: answerCommand, status: statusCommand)
        XCTAssertEqual(feed.answers["DAT-30"]?.text, "Answered: no, picked up on the next tick")
    }

    @MainActor func testFailureShowsTheCommandOutputAndRecordsNoAnswer() async throws {
        let calls = Calls()
        let feed = feed(answer: CommandResult(status: 2, stdout: "", stderr: "Expected one ticket for 'DAT-30'"), calls: calls)
        await feed.refresh(statusCommand)
        let ticket = try XCTUnwrap(feed.queue?.decisions.first)
        await feed.answer(ticket, go: true, note: "", command: answerCommand, status: statusCommand)
        XCTAssertEqual(feed.errors["DAT-30"], "Expected one ticket for 'DAT-30'")
        XCTAssertNil(feed.answers["DAT-30"])
        let ran = await calls.commands
        XCTAssertEqual(ran, [statusCommand, answerCommand], "no refresh after a failure")
    }

    @MainActor func testAnAnsweredTicketIsNotAnsweredAgain() async throws {
        let calls = Calls()
        let feed = feed(answer: CommandResult(status: 0, stdout: "", stderr: ""), calls: calls)
        await feed.refresh(statusCommand)
        let ticket = try XCTUnwrap(feed.queue?.decisions.first)
        await feed.answer(ticket, go: true, note: "", command: answerCommand, status: statusCommand)
        await feed.answer(ticket, go: false, note: "", command: answerCommand, status: statusCommand)
        let ran = await calls.commands.filter { $0 == answerCommand }
        XCTAssertEqual(ran.count, 1)
    }

    @MainActor func testAnsweredCardStaysAfterTheTicketLeavesTheWaitingList() async throws {
        let gone = "{\"version\":1,\"groups\":{\"waiting\":[]},\"tickets\":[]}"
        let status = String(decoding: fixture(), as: UTF8.self)
        let state = Counter()
        let statusCommand = self.statusCommand
        let feed = DecisionsFeed(run: { command in
            if command == statusCommand {
                return CommandResult(status: 0, stdout: await state.bump() == 1 ? status : gone, stderr: "")
            }
            return CommandResult(status: 0, stdout: "", stderr: "")
        })
        await feed.refresh(statusCommand)
        let ticket = try XCTUnwrap(feed.queue?.decisions.first)
        await feed.answer(ticket, go: true, note: "", command: answerCommand, status: statusCommand)
        XCTAssertTrue(feed.queue?.decisions.isEmpty ?? false)
        XCTAssertEqual(feed.cards.map(\.ticket.id), ["DAT-30"])
        XCTAssertNotNil(feed.cards.first?.answer)
    }
}

private actor Calls {
    private(set) var commands: [Command] = []
    func record(_ command: Command) { commands.append(command) }
}

private actor Counter {
    private var n = 0
    func bump() -> Int { n += 1; return n }
}
