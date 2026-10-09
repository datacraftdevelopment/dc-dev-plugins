import SwiftUI
import RunwayCore

/// The red flag on a ticket whose latest attempt didn't merge, with the kind in words.
struct ErroredFlag: View {
    let kind: String
    var compact = false

    var body: some View {
        Label(ErroredKind.words(kind), systemImage: "flag.fill")
            .font(compact ? .caption2.bold() : .caption.bold())
            .foregroundStyle(.red)
            .help("The latest attempt didn't merge: \(ErroredKind.words(kind))")
    }
}

/// "Talk it through": opens Terminal on `runway discuss` for a ticket, or for the loop when `ticket` is nil.
/// A failed launch shows its output beside the button, like a failed Go.
struct TalkButton: View {
    let store: ProjectStore
    let project: Project
    var ticket: String?

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Button("Talk it through") {
                Task {
                    if let ticket { await store.talkThrough(ticket: ticket, in: project) }
                    else { await store.talkThroughLoop(project) }
                }
            }
            .disabled(project.repoPath == nil)
            .help(ticket == nil ? "Open Terminal on `runway discuss --loop`" : "Open Terminal on `runway discuss \(ticket ?? "")`")
            if let error = store.talkError(project: project, ticket: ticket) {
                Text(error).font(.caption2.monospaced()).textSelection(.enabled).padding(6)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(.red.opacity(0.15), in: RoundedRectangle(cornerRadius: 6))
            }
        }
    }
}
