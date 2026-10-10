import AppKit
import SwiftUI
import SwiftTerm
import RunwayCore

/// Keeps one terminal view per session, so switching tabs doesn't restart or blank a running `claude`.
@MainActor
final class TerminalHost {
    static let shared = TerminalHost()
    private var views: [UUID: LocalProcessTerminalView] = [:]
    private var delegates: [UUID: ExitWatcher] = [:]

    func view(for session: Session, registry: SessionRegistry) -> LocalProcessTerminalView {
        if let view = views[session.id] { return view }
        let view = LocalProcessTerminalView(frame: NSRect(x: 0, y: 0, width: 600, height: 240))
        let watcher = ExitWatcher(id: session.id, registry: registry)
        view.processDelegate = watcher
        delegates[session.id] = watcher
        views[session.id] = view
        view.startProcess(executable: session.spec.executable, args: session.spec.arguments,
                          currentDirectory: session.spec.workingDirectory)
        return view
    }

    /// Ends the process (if still running) and forgets the view.
    func end(_ id: UUID) {
        delegates[id]?.silenced = true
        views[id]?.terminate()
        views[id] = nil
        delegates[id] = nil
    }

    func endAll() { Array(views.keys).forEach(end) }
}

final class ExitWatcher: NSObject, LocalProcessTerminalViewDelegate {
    let id: UUID
    let registry: SessionRegistry
    var silenced = false

    init(id: UUID, registry: SessionRegistry) {
        self.id = id
        self.registry = registry
    }

    func sizeChanged(source: LocalProcessTerminalView, newCols: Int, newRows: Int) {}
    func setTerminalTitle(source: LocalProcessTerminalView, title: String) {}
    func hostCurrentDirectoryUpdate(source: TerminalView, directory: String?) {}

    func processTerminated(source: TerminalView, exitCode: Int32?) {
        Task { @MainActor in
            if !silenced { registry.markExited(id) }
        }
    }
}

struct TerminalViewRepresentable: NSViewRepresentable {
    let session: Session
    let registry: SessionRegistry

    func makeNSView(context: Context) -> NSView {
        let container = NSView()
        attach(to: container)
        return container
    }

    func updateNSView(_ container: NSView, context: Context) { attach(to: container) }

    private func attach(to container: NSView) {
        let view = TerminalHost.shared.view(for: session, registry: registry)
        guard view.superview !== container else { return }
        container.subviews.forEach { $0.removeFromSuperview() }
        view.frame = container.bounds
        view.autoresizingMask = [.width, .height]
        container.addSubview(view)
        DispatchQueue.main.async { view.window?.makeFirstResponder(view) }
    }
}

/// The terminal pane docked at the bottom of the Runway window: one tab per session.
struct SessionPane: View {
    let store: ProjectStore
    @State private var confirmClose: Session?
    @State private var confirmPopOut: Session?

    private var registry: SessionRegistry { store.sessions }

    var body: some View {
        VStack(spacing: 0) {
            HStack(spacing: 4) {
                ForEach(registry.sessions) { session in tab(session) }
                Spacer()
                if let selected = registry.sessions.first(where: { $0.id == registry.selected }) {
                    Button("Pop out to Terminal") { ask(selected, popOut: true) }
                        .buttonStyle(.borderless).font(.caption)
                        .help("End this session and reopen it in Terminal.app")
                }
            }
            .padding(.horizontal, 8).padding(.vertical, 4)
            Divider()
            ZStack {
                ForEach(registry.sessions) { session in
                    TerminalViewRepresentable(session: session, registry: registry)
                        .opacity(session.id == registry.selected ? 1 : 0)
                        .allowsHitTesting(session.id == registry.selected)
                }
            }
        }
        .frame(height: 280)
        .background(.background)
        .confirmationDialog("End this session?", isPresented: Binding(
            get: { confirmClose != nil }, set: { if !$0 { confirmClose = nil } }), presenting: confirmClose) { session in
            Button("End \(session.title)", role: .destructive) { close(session) }
        } message: { session in
            Text("\(session.title) is still running. Closing the tab ends it.")
        }
        .confirmationDialog("Pop out to Terminal?", isPresented: Binding(
            get: { confirmPopOut != nil }, set: { if !$0 { confirmPopOut = nil } }), presenting: confirmPopOut) { session in
            Button("End here and open in Terminal") { popOut(session) }
        } message: { session in
            Text("This ends the session in the pane. Terminal starts \(session.title) again from the top.")
        }
    }

    private func tab(_ session: Session) -> some View {
        let selected = session.id == registry.selected
        return HStack(spacing: 4) {
            Circle().fill(session.alive ? Color.green : Color.secondary).frame(width: 6, height: 6)
            Text(session.title).font(.callout.weight(selected ? .semibold : .regular))
            Button { ask(session, popOut: false) } label: { Image(systemName: "xmark") }
                .buttonStyle(.borderless).font(.caption2).help("Close this tab")
        }
        .padding(.horizontal, 8).padding(.vertical, 3)
        .background(selected ? Color.accentColor.opacity(0.18) : .clear, in: Capsule())
        .contentShape(Capsule())
        .onTapGesture { registry.selected = session.id }
    }

    private func ask(_ session: Session, popOut: Bool) {
        if popOut { confirmPopOut = session }
        else if session.alive { confirmClose = session }
        else { close(session) }
    }

    private func close(_ session: Session) {
        TerminalHost.shared.end(session.id)
        registry.close(session.id)
    }

    private func popOut(_ session: Session) {
        TerminalHost.shared.end(session.id)
        Task { await store.popOut(session.id) }
    }
}

/// Asks before quitting while sessions are live; they end with the app.
final class QuitGuard: NSObject, NSApplicationDelegate {
    @MainActor static var store: ProjectStore?

    func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
        MainActor.assumeIsolated {
            guard let store = Self.store, store.sessions.liveCount > 0 else { return .terminateNow }
            let alert = NSAlert()
            alert.messageText = "Quit Runway?"
            alert.informativeText = "\(store.sessions.liveCount) Claude session(s) are running in the Runway window. They will end when it quits."
            alert.addButton(withTitle: "Cancel")
            alert.addButton(withTitle: "Quit and end sessions")
            guard alert.runModal() == .alertSecondButtonReturn else { return .terminateCancel }
            TerminalHost.shared.endAll()
            return .terminateNow
        }
    }
}
