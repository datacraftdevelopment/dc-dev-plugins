import Foundation
import Observation

/// A decision packet broken into the blocks the Decisions tab draws. Inline Markdown (bold, code, links) stays in the text.
public enum PacketBlock: Equatable, Sendable {
    case heading(level: Int, text: String)
    case paragraph(String)
    case bullet(String)
    case numbered(number: Int, text: String)
    case code(String)
}

public enum PacketMarkdown {
    public static func blocks(_ markdown: String) -> [PacketBlock] {
        var blocks: [PacketBlock] = []
        var paragraph: [String] = []
        var code: [String]?

        func flush() {
            if !paragraph.isEmpty { blocks.append(.paragraph(paragraph.joined(separator: " "))) }
            paragraph = []
        }

        for raw in markdown.replacingOccurrences(of: "\r\n", with: "\n").components(separatedBy: "\n") {
            let line = raw.trimmingCharacters(in: .whitespaces)
            if line.hasPrefix("```") {
                if let open = code {
                    blocks.append(.code(open.joined(separator: "\n")))
                    code = nil
                } else {
                    flush()
                    code = []
                }
            } else if code != nil {
                code?.append(raw)
            } else if line.isEmpty {
                flush()
            } else if let heading = heading(line) {
                flush()
                blocks.append(heading)
            } else if let item = listItem(line) {
                flush()
                blocks.append(item)
            } else {
                paragraph.append(line)
            }
        }
        if let open = code { blocks.append(.code(open.joined(separator: "\n"))) }
        flush()
        return blocks
    }

    /// The prep prompt asks the agent to mark its recommendation; this spots it in an option line.
    public static func isRecommended(_ text: String) -> Bool {
        text.range(of: "recommend", options: .caseInsensitive) != nil
    }

    private static func heading(_ line: String) -> PacketBlock? {
        let hashes = line.prefix { $0 == "#" }.count
        guard (1...6).contains(hashes), line.dropFirst(hashes).first == " " else { return nil }
        return .heading(level: hashes, text: line.dropFirst(hashes).trimmingCharacters(in: .whitespaces))
    }

    private static func listItem(_ line: String) -> PacketBlock? {
        if let marker = line.first, "-*+".contains(marker), line.dropFirst().first == " " {
            return .bullet(line.dropFirst(2).trimmingCharacters(in: .whitespaces))
        }
        let digits = line.prefix { $0.isNumber }
        let rest = line.dropFirst(digits.count)
        if let number = Int(digits), let mark = rest.first, ".)".contains(mark), rest.dropFirst().first == " " {
            return .numbered(number: number, text: rest.dropFirst(2).trimmingCharacters(in: .whitespaces))
        }
        return nil
    }
}

/// What Joe answered, kept so the card can say so after the ticket leaves the waiting list.
public struct DecisionAnswer: Equatable, Sendable {
    public let go: Bool
    public let note: String

    public var text: String {
        "Answered: \(go ? "go" : "no")\(note.isEmpty ? "" : " “\(note)”"), picked up on the next tick"
    }
}

public struct DecisionCard: Equatable, Sendable, Identifiable {
    public var id: String { ticket.id }
    public let ticket: QueueTicket
    public let answer: DecisionAnswer?
}

/// The Decisions tab's state. Nothing here sends an answer except `answer(_:go:…)`, which a button calls for one ticket.
@MainActor @Observable
public final class DecisionsFeed {
    public private(set) var queue: QueueStatus?
    public private(set) var fetchedAt: Date?
    public private(set) var error: String?
    public private(set) var isRefreshing = false
    public private(set) var answers: [String: DecisionAnswer] = [:]
    /// The output of a failed `runway go|no`, by ticket.
    public private(set) var errors: [String: String] = [:]
    @ObservationIgnored private var answering: Set<String> = []
    @ObservationIgnored private var answered: [String: QueueTicket] = [:]

    @ObservationIgnored private let run: @Sendable (Command) async -> CommandResult
    @ObservationIgnored private let now: @Sendable () -> Date

    public init(run: @escaping @Sendable (Command) async -> CommandResult = { await CommandRunner.run($0) },
                now: @escaping @Sendable () -> Date = { Date() }) {
        self.run = run
        self.now = now
    }

    public func isAnswering(_ id: String) -> Bool { answering.contains(id) }

    /// Waiting tickets, then tickets answered here that have since left the list, so "Answered" stays on screen.
    public var cards: [DecisionCard] {
        let waiting = queue?.decisions ?? []
        let ids = Set(waiting.map(\.id))
        let gone = answered.values.filter { !ids.contains($0.id) }.sorted { $0.id < $1.id }
        return (waiting + gone).map { DecisionCard(ticket: $0, answer: answers[$0.id]) }
    }

    /// Reads status only. A refresh already under way wins.
    public func refresh(_ command: Command) async {
        guard !isRefreshing else { return }
        isRefreshing = true
        defer { isRefreshing = false }
        let result = await run(command)
        if !result.succeeded {
            error = result.failureMessage
        } else if let parsed = QueueStatus.parse(Data(result.stdout.utf8)) {
            queue = parsed
            fetchedAt = now()
            error = nil
        } else {
            error = "Couldn't read the status output."
        }
    }

    /// Runs `command` (the `runway go|no` for this ticket) once, then refreshes status. A failure keeps its output
    /// beside the card and records no answer. A ticket already answered here is left alone.
    public func answer(_ ticket: QueueTicket, go: Bool, note: String, command: Command, status: Command) async {
        guard answers[ticket.id] == nil, !answering.contains(ticket.id) else { return }
        answering.insert(ticket.id)
        defer { answering.remove(ticket.id) }
        let result = await run(command)
        guard result.succeeded else {
            errors[ticket.id] = result.failureMessage
            return
        }
        errors[ticket.id] = nil
        answers[ticket.id] = DecisionAnswer(go: go, note: note.trimmingCharacters(in: .whitespacesAndNewlines))
        answered[ticket.id] = ticket
        await refresh(status)
    }
}
