import Foundation

/// One ticket waiting on Joe, as the side panel's "Needs you" section shows it.
public struct NeedsYouRow: Equatable, Sendable, Identifiable {
    public let id: String
    public let title: String
    /// Why it waits: status's `reason` when it has one, else `waiting_on`.
    public let reason: String?
    /// The packet's recommended option, one line, when the packet marks one.
    public let recommended: String?
    public let url: URL?

    init(entry: [String: Any], url: URL?) {
        id = (entry["id"] as? String) ?? ""
        title = (entry["title"] as? String) ?? ""
        let reason = (entry["reason"] as? String).flatMap { $0.isEmpty ? nil : $0 }
        self.reason = reason ?? (entry["waiting_on"] as? String).flatMap { $0.isEmpty ? nil : $0 }
        recommended = (entry["packet"] as? String).flatMap(Self.recommendation)
        self.url = url
    }

    /// The ticket as `DecisionsFeed.answer` keeps it, so "Answered" outlives the ticket's place in the waiting list.
    public var queueTicket: QueueTicket {
        QueueTicket(id: id, title: title, url: url?.absoluteString, status: "needs-human", gate: "", blockedBy: [],
                    waitingOn: reason, harness: nil, packet: nil)
    }

    /// The first option line the packet marks as recommended.
    static func recommendation(_ packet: String) -> String? {
        for block in PacketMarkdown.blocks(packet) {
            switch block {
            case .bullet(let text), .numbered(_, let text):
                if PacketMarkdown.isRecommended(text) { return text }
            default: break
            }
        }
        return nil
    }

    /// Empty when nothing waits (or there is no status yet), so the panel draws no section.
    public static func rows(from snapshot: StatusSnapshot?) -> [NeedsYouRow] { snapshot?.needsYou ?? [] }
}
