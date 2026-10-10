import Foundation
import Observation

/// Where "Talk it through" opens its Claude session.
public enum SessionPlace: String, CaseIterable, Sendable {
    case window, terminal
}

/// What the pane's PTY runs: a login shell, so PATH, `claude`, `ringer` and `gh` match what the loop sees.
public struct LaunchSpec: Equatable, Sendable {
    public let executable: String
    public let arguments: [String]
    public let workingDirectory: String
}

extension RunwayTools {
    /// The same command as `discuss(ticket:repo:)`, run in the pane instead of Terminal.
    public func discussSession(ticket: String, repo: String) -> LaunchSpec {
        spec(repo: repo, discussTail(ticket: ticket))
    }

    public func discussLoopSession(repo: String) -> LaunchSpec {
        spec(repo: repo, "discuss --loop")
    }

    private func spec(repo: String, _ tail: String) -> LaunchSpec {
        LaunchSpec(executable: "/bin/zsh", arguments: ["-lc", shellLine(repo: repo, tail)], workingDirectory: repo)
    }
}

public struct Session: Identifiable, Equatable, Sendable {
    public let id: UUID
    public let project: String
    /// nil for the loop (`discuss --loop`).
    public let ticket: String?
    public let spec: LaunchSpec
    public var alive = true

    public var title: String { ticket ?? "loop" }
}

/// The tabs of the terminal pane. One live tab per ticket (or per project's loop); a tab whose process
/// has exited stays until closed, but a new request starts a fresh one.
@MainActor @Observable
public final class SessionRegistry {
    public private(set) var sessions: [Session] = []
    public var selected: UUID?

    public init() {}

    public var liveCount: Int { sessions.filter(\.alive).count }

    @discardableResult
    public func open(project: String, ticket: String?, spec: LaunchSpec) -> Session {
        if let existing = sessions.first(where: { $0.alive && $0.project == project && $0.ticket == ticket }) {
            selected = existing.id
            return existing
        }
        let session = Session(id: UUID(), project: project, ticket: ticket, spec: spec)
        sessions.append(session)
        selected = session.id
        return session
    }

    public func markExited(_ id: UUID) {
        guard let index = sessions.firstIndex(where: { $0.id == id }) else { return }
        sessions[index].alive = false
    }

    public func close(_ id: UUID) {
        guard let index = sessions.firstIndex(where: { $0.id == id }) else { return }
        sessions.remove(at: index)
        if selected == id { selected = sessions.last?.id }
    }
}
