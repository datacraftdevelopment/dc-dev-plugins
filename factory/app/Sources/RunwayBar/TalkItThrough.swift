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

/// "Talk it through": starts `runway discuss` (in the Runway window's pane or in Terminal, per the setting) for a ticket, or for the loop when `ticket` is nil.
/// A failed launch shows its output beside the button, like a failed Go.
struct TalkButton: View {
    let store: ProjectStore
    let project: Project
    var ticket: String?
    /// Adds "Resume worker" beside the button: the ticket's latest attempt is a claude session the engine can reopen.
    var resumable = false
    @Environment(\.openWindow) private var openWindow

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack(spacing: 10) {
                Button("Talk it through") {
                    Task {
                        if let ticket { await store.talkThrough(ticket: ticket, in: project) }
                        else { await store.talkThroughLoop(project) }
                        showPane()
                    }
                }
                .disabled(project.repoPath == nil)
                .help(ticket == nil ? "Open Terminal on `runway discuss --loop`" : "Open Terminal on `runway discuss \(ticket ?? "")`")
                if let ticket, resumable {
                    Button("Resume worker") {
                        Task {
                            await store.resumeWorker(ticket: ticket, in: project)
                            showPane()
                        }
                    }
                    .disabled(project.repoPath == nil)
                    .help("Reopen the worker's own Claude conversation: `runway discuss \(ticket) --resume`")
                }
            }
            if let error = store.talkError(project: project, ticket: ticket) { errorBox(error) }
            if let ticket, resumable, let error = store.talkError(project: project, ticket: ticket, resume: true) {
                errorBox(error)
            }
        }
    }

    /// The session lives in the Runway window's pane, so bring that window up (the side panel is another one).
    private func showPane() {
        if store.sessionPlace == .window {
            NSApplication.shared.activate(ignoringOtherApps: true)
            openWindow(id: "runway")
        }
    }

    private func errorBox(_ error: String) -> some View {
        Text(error).font(.caption2.monospaced()).textSelection(.enabled).padding(6)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(.red.opacity(0.15), in: RoundedRectangle(cornerRadius: 6))
    }
}
