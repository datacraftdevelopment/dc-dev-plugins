import SwiftUI
import RunwayCore

/// State for the "This Mac" sheet. The logic lives in RunwayCore (`MachineRules`, `MachineFile`, `MachineStore`).
@MainActor @Observable
final class MachineModel {
    let store: ProjectStore
    var rules = MachineRules()
    private(set) var loadError: String?
    private(set) var saveError: String?
    private(set) var saved = false
    private(set) var status: String?
    private let files = MachineStore()

    init(store: ProjectStore) {
        self.store = store
    }

    var problems: [String] { rules.problems }
    var canSave: Bool { loadError == nil && problems.isEmpty }

    func load() async {
        do { rules = try files.load() } catch { loadError = error.localizedDescription }
        await refreshStatus()
    }

    func save() async {
        saved = false
        saveError = nil
        do {
            try files.save(rules)
            saved = true
        } catch {
            saveError = error.localizedDescription
        }
        await refreshStatus()
    }

    func refreshStatus() async {
        guard let tools = store.tools else { status = nil; return }
        let result = await CommandRunner.run(tools.machine())
        status = result.succeeded ? result.stdout : result.failureMessage
    }

    func toggle(day: String) {
        if let index = rules.quietDays.firstIndex(of: day) {
            rules.quietDays.remove(at: index)
        } else {
            rules.quietDays = MachineRules.allDays.filter { $0 == day || rules.quietDays.contains($0) }
        }
    }
}

struct MachineSheet: View {
    @State private var model: MachineModel
    @Environment(\.dismiss) private var dismiss

    init(store: ProjectStore) {
        _model = State(initialValue: MachineModel(store: store))
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            Text("This Mac").font(.title2.bold()).padding([.top, .horizontal], 16)
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    if let error = model.loadError {
                        banner("\(error) Saving is off until it's fixed or removed.", color: .red)
                    }
                    quietSection
                    otherSection
                    ChoresSection(store: model.store, close: { dismiss() })
                    statusSection
                }
                .padding(16)
            }
            Divider()
            HStack {
                if let error = model.saveError {
                    Text(error).font(.caption).foregroundStyle(.red).lineLimit(2)
                } else if model.saved {
                    Text("Saved to ~/.runway/machine.json").font(.caption).foregroundStyle(.secondary)
                }
                Spacer()
                Button("Close") { dismiss() }.keyboardShortcut(.cancelAction)
                Button("Save") { Task { await model.save() } }
                    .keyboardShortcut(.defaultAction)
                    .disabled(!model.canSave)
            }
            .padding(12)
        }
        .frame(width: 520, height: 600)
        .task { await model.load() }
    }

    private var quietSection: some View {
        VStack(alignment: .leading, spacing: 8) {
            Toggle("Quiet hours (don't start new tickets)", isOn: $model.rules.quietEnabled).font(.headline)
            HStack {
                TextField("From", text: $model.rules.quietFrom).textFieldStyle(.roundedBorder).frame(width: 80)
                Text("to")
                TextField("To", text: $model.rules.quietTo).textFieldStyle(.roundedBorder).frame(width: 80)
                Text("24-hour, like 09:00").font(.caption).foregroundStyle(.secondary)
            }
            .disabled(!model.rules.quietEnabled)
            HStack(spacing: 4) {
                ForEach(MachineRules.allDays, id: \.self) { day in
                    Toggle(day.capitalized, isOn: Binding(
                        get: { model.rules.quietDays.contains(day) },
                        set: { _ in model.toggle(day: day) }))
                    .toggleStyle(.button)
                }
            }
            .disabled(!model.rules.quietEnabled)
            ForEach(model.problems, id: \.self) { Text($0).font(.caption).foregroundStyle(.orange) }
        }
    }

    private var otherSection: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Toggle("Only when idle for", isOn: $model.rules.idleEnabled)
                Stepper("\(model.rules.idleMinutes) min", value: $model.rules.idleMinutes, in: 1...240, step: 5)
                    .disabled(!model.rules.idleEnabled)
            }
            Toggle("Not on battery", isOn: $model.rules.notOnBattery)
            Stepper(model.rules.maxAgents == 0 ? "Max agents: no limit" : "Max agents: \(model.rules.maxAgents)",
                    value: $model.rules.maxAgents, in: 0...16)
            Picker("When paused", selection: $model.rules.pauseMode) {
                Text("Let the ticket finish").tag(MachineRules.PauseMode.finish)
                Text("Stop now").tag(MachineRules.PauseMode.stop)
            }
            .pickerStyle(.segmented)
        }
    }

    private var statusSection: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("runway machine").font(.headline)
            Text(model.status ?? "Clone the engine first (Set up a loop…).")
                .font(.system(size: 11, design: .monospaced)).textSelection(.enabled)
                .frame(maxWidth: .infinity, alignment: .leading).padding(8)
                .background(.black.opacity(0.06), in: RoundedRectangle(cornerRadius: 6))
        }
    }

    private func banner(_ text: String, color: Color) -> some View {
        Text(text).padding(8).frame(maxWidth: .infinity, alignment: .leading)
            .background(color.opacity(0.2), in: RoundedRectangle(cornerRadius: 6))
    }
}

/// The engine checkout's chores (`pm/runway/chores.json`) whose `show_if` passes. Run shows the exact line first, asks
/// again for a chore marked `confirm`, then closes this sheet (it's modal over the pane) and runs it in the window's pane.
struct ChoresSection: View {
    let store: ProjectStore
    let close: () -> Void
    @State private var shown: [Chore]?
    @State private var asking: Chore?

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Chores").font(.headline)
            switch store.choreList() {
            case .unusable(let why):
                Text(why).font(.caption).foregroundStyle(.secondary)
            case .chores:
                if let shown {
                    if shown.isEmpty { Text("Nothing to do on this Mac right now.").font(.caption).foregroundStyle(.secondary) }
                    ForEach(shown) { chore in row(chore) }
                } else {
                    HStack(spacing: 6) { ProgressView().controlSize(.small); Text("Checking…").font(.caption) }
                }
            }
        }
        .task { shown = await store.visibleChores(.checkout) }
        .confirmationDialog(asking?.title ?? "", isPresented: Binding(
            get: { asking != nil }, set: { if !$0 { asking = nil } }), presenting: asking) { chore in
            Button("Run it") { start(chore) }
        } message: { chore in
            Text(store.choreLine(chore) ?? chore.run)
        }
    }

    private func row(_ chore: Chore) -> some View {
        VStack(alignment: .leading, spacing: 3) {
            HStack {
                Text(chore.title).font(.callout.weight(.medium))
                Spacer()
                Button("Run") { if chore.confirm { asking = chore } else { start(chore) } }
            }
            if !chore.why.isEmpty { Text(chore.why).font(.caption).foregroundStyle(.secondary) }
            Text(store.choreLine(chore) ?? chore.run).font(.system(size: 10, design: .monospaced))
                .foregroundStyle(.secondary).textSelection(.enabled).lineLimit(3)
            if let result = store.choreResult(chore) { Text(result).font(.caption).foregroundStyle(.green) }
        }
        .padding(8)
        .background(.black.opacity(0.04), in: RoundedRectangle(cornerRadius: 6))
    }

    private func start(_ chore: Chore) {
        store.runChore(chore)
        close()
    }
}

