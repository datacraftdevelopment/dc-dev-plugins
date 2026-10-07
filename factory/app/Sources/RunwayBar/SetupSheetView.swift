import AppKit
import SwiftUI
import RunwayCore

/// State for the "Set up a loop" sheet. The logic lives in RunwayCore (`SetupChecks`, `SetupPlan`, `SetupRunner`).
@MainActor @Observable
final class SetupModel {
    let store: ProjectStore
    var repo = ""
    var tracker: SetupTracker = .linear
    var team = ""
    var project = ""
    var harness = "claude"
    var minutes = 10
    /// Bound to a SecureField and cleared as soon as it is saved. Never stored anywhere else.
    var keyInput = ""
    private(set) var checks: [SetupCheck] = []
    private(set) var log: [String] = []
    private(set) var running = false
    private(set) var outcome: SetupOutcome?
    private(set) var note: String?

    init(store: ProjectStore) {
        self.store = store
    }

    var config: SetupConfig {
        SetupConfig(repo: repo, tracker: tracker, team: team, project: project, harness: harness, minutes: minutes)
    }

    private var checkout: String? {
        store.checkout ?? store.tools.map { SetupChecks.checkout(ofRunwayScript: $0.runwayScript) }
    }

    var steps: [SetupStep] {
        checkout.map { SetupPlan.steps(config, tools: RunwayTools(checkout: $0)) } ?? []
    }

    var harnesses: [String] {
        ["claude"] + ["codex", "cursor-agent"].filter { name in checks.contains { $0.id == name && $0.status == .ok } }
    }

    var blocked: Bool { !SetupChecks.blocking(checks).isEmpty }
    var canRun: Bool { !running && !blocked && SetupPlan.problems(config).isEmpty && !steps.isEmpty }

    func refreshChecks() async {
        checks = await SetupChecks.all(tracker: tracker, checkout: checkout,
                                       fileExists: { FileManager.default.fileExists(atPath: $0) },
                                       run: { await CommandRunner.run($0) })
        if !harnesses.contains(harness) { harness = "claude" }
    }

    func chooseRepo() {
        if let path = pickFolder("Pick the repo folder (it is created if it doesn't exist yet).") { repo = path }
    }

    func clone() async {
        guard let folder = pickFolder("Pick the folder to clone dc-dev-plugins into.") else { return }
        append("$ git clone \(SetupChecks.engineURL)")
        let result = await CommandRunner.stream(SetupChecks.cloneCommand(into: folder)) { [weak self] line in
            Task { @MainActor in self?.append(line) }
        }
        if result.succeeded {
            store.setCheckout(SetupChecks.clonedCheckout(into: folder))
            note = nil
        } else {
            note = "Clone failed: see the output below."
        }
        await refreshChecks()
    }

    func openTerminalToSignIn() async {
        _ = await CommandRunner.run(SetupChecks.signInCommand)
        note = "Terminal is open. Sign in there, then come back."
    }

    func saveKey() async {
        let key = keyInput
        keyInput = ""
        append("$ " + LinearKey.displayText())
        let result = await LinearKey.save(key, run: { await CommandRunner.run($0) })
        if !result.succeeded { append(result.failureMessage) }
        note = result.succeeded ? nil : "Couldn't save the key: \(result.failureMessage)"
        await refreshChecks()
    }

    func run() async {
        guard canRun else { return }
        running = true
        outcome = nil
        note = nil
        log = []
        let result = await SetupRunner.run(
            steps,
            execute: { command, onLine in await CommandRunner.stream(command, onLine: onLine) },
            output: { [weak self] line in Task { @MainActor in self?.append(line) } })
        outcome = result
        running = false
        if case .completed = result { store.refresh() }
        await refreshChecks()
    }

    private func append(_ line: String) {
        log.append(line)
        if log.count > 2000 { log.removeFirst(log.count - 2000) }
    }

    private func pickFolder(_ message: String) -> String? {
        let panel = NSOpenPanel()
        panel.canChooseDirectories = true
        panel.canChooseFiles = false
        panel.canCreateDirectories = true
        panel.prompt = "Choose"
        panel.message = message
        return panel.runModal() == .OK ? panel.url?.path : nil
    }
}

struct SetupSheet: View {
    @State private var model: SetupModel
    @Environment(\.dismiss) private var dismiss

    init(store: ProjectStore) {
        _model = State(initialValue: SetupModel(store: store))
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            Text("Set up a loop").font(.title2.bold()).padding([.top, .horizontal], 16)
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    checksSection
                    projectSection
                    commandsSection
                    outputSection
                }
                .padding(16)
            }
            Divider()
            HStack {
                if let note = model.note { Text(note).font(.caption).foregroundStyle(.secondary).lineLimit(2) }
                Spacer()
                Button("Close") { dismiss() }.keyboardShortcut(.cancelAction)
                Button(model.outcome == nil ? "Run" : "Run again") { Task { await model.run() } }
                    .keyboardShortcut(.defaultAction)
                    .disabled(!model.canRun)
            }
            .padding(12)
        }
        .frame(width: 620, height: 640)
        .task { await model.refreshChecks() }
        .onChange(of: model.tracker) { _, _ in Task { await model.refreshChecks() } }
    }

    // MARK: sections

    private var checksSection: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("This Mac").font(.headline)
            ForEach(model.checks) { check in
                HStack(alignment: .firstTextBaseline) {
                    Image(systemName: check.status == .ok ? "checkmark.circle.fill" : (check.required ? "xmark.circle.fill" : "minus.circle"))
                        .foregroundStyle(check.status == .ok ? .green : (check.required ? .red : .secondary))
                    Text(check.title)
                    Text(check.detail).font(.caption).foregroundStyle(.secondary).lineLimit(1)
                    Spacer()
                    fixButton(check)
                }
                if check.fix == .saveKey { keyField }
            }
            if model.checks.isEmpty { ProgressView().controlSize(.small) }
        }
    }

    @ViewBuilder private func fixButton(_ check: SetupCheck) -> some View {
        switch check.fix {
        case .cloneEngine: Button("Clone…") { Task { await model.clone() } }
        case .signIn: Button("Open Terminal to sign in") { Task { await model.openTerminalToSignIn() } }
        case .saveKey, .none: EmptyView()
        }
    }

    private var keyField: some View {
        HStack {
            SecureField("Paste the Linear API key", text: $model.keyInput).textFieldStyle(.roundedBorder)
            Button("Save to keychain") { Task { await model.saveKey() } }
                .disabled(model.keyInput.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
        }
    }

    private var projectSection: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Project").font(.headline)
            HStack {
                TextField("Repo folder", text: $model.repo).textFieldStyle(.roundedBorder)
                Button("Choose…") { model.chooseRepo() }
            }
            Picker("Tracker", selection: $model.tracker) {
                Text("Linear").tag(SetupTracker.linear)
                Text("git").tag(SetupTracker.git)
            }
            .pickerStyle(.segmented)
            if model.tracker == .linear {
                HStack {
                    TextField("Team key (e.g. DAT)", text: $model.team).textFieldStyle(.roundedBorder).frame(width: 160)
                    TextField("Linear project name", text: $model.project).textFieldStyle(.roundedBorder)
                }
            }
            HStack {
                Picker("Harness", selection: $model.harness) {
                    ForEach(model.harnesses, id: \.self) { Text($0).tag($0) }
                }
                .frame(width: 220)
                Stepper("Every \(model.minutes) min", value: $model.minutes, in: 1...240, step: 5)
            }
            ForEach(SetupPlan.problems(model.config), id: \.self) {
                Text($0).font(.caption).foregroundStyle(.orange)
            }
        }
    }

    private var commandsSection: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Commands it will run").font(.headline)
            if model.steps.isEmpty {
                Text("Clone the engine first.").font(.caption).foregroundStyle(.secondary)
            }
            ForEach(Array(model.steps.enumerated()), id: \.element.id) { index, step in
                VStack(alignment: .leading, spacing: 2) {
                    Text("\(index + 1). \(step.title)").font(.caption.bold())
                    Text(step.display).font(.system(size: 11, design: .monospaced)).textSelection(.enabled)
                }
            }
        }
    }

    @ViewBuilder private var outputSection: some View {
        if model.running || !model.log.isEmpty || model.outcome != nil {
            VStack(alignment: .leading, spacing: 6) {
                Text("Output").font(.headline)
                if case .failed(let step, _)? = model.outcome {
                    banner("Stopped at “\(step.title)”. Fix it and run again; every step is safe to repeat.", color: .red)
                }
                if case .completed(let warnings)? = model.outcome {
                    banner("Loop set up.", color: .green)
                    if !warnings.isEmpty {
                        banner("Claimed by another Mac, so this one will skip them: "
                               + warnings.map { "\($0.ticket) (\($0.machine))" }.joined(separator: ", "), color: .orange)
                    }
                }
                ScrollViewReader { proxy in
                    ScrollView {
                        Text(model.log.joined(separator: "\n"))
                            .font(.system(size: 11, design: .monospaced)).textSelection(.enabled)
                            .frame(maxWidth: .infinity, alignment: .leading).id("end")
                    }
                    .frame(height: 160).padding(8)
                    .background(.black.opacity(0.06), in: RoundedRectangle(cornerRadius: 6))
                    .onChange(of: model.log.count) { _, _ in proxy.scrollTo("end", anchor: .bottom) }
                }
            }
        }
    }

    private func banner(_ text: String, color: Color) -> some View {
        Text(text).padding(8).frame(maxWidth: .infinity, alignment: .leading)
            .background(color.opacity(0.2), in: RoundedRectangle(cornerRadius: 6))
    }
}
