import Foundation
import Observation

/// A project with its resolved state, one row of the menu.
public struct ProjectEntry: Identifiable, Equatable, Sendable {
    public var id: String { project.label }
    public let project: Project
    public let status: ProjectStatus
}

/// Holds the discovered projects for the views. Refreshes on a timer and when anything in a repo's `_pm/` changes,
/// and runs the menu's commands (start, stop, run now, pause, resume).
@MainActor
@Observable
public final class ProjectStore {
    public private(set) var projects: [Project] = []
    public private(set) var entries: [ProjectEntry] = []
    public private(set) var pause: PauseInfo?
    public private(set) var overall: OverallState = .allOff
    public private(set) var badge = 0
    /// A project has ready tickets but its loop is off. Drives the amber icon; independent of notifications.
    public private(set) var readyWhileOff = false
    /// Set when a notification is clicked: the tab the window should open on.
    public var requestedRoute: NotificationRoute?
    /// The last command's stderr when it failed; cleared by the next success or `dismissError()`.
    public private(set) var lastError: String?
    /// The dc-dev-plugins checkout holding `schedule.sh` and `runway.py`; nil means the one the plists point at.
    public private(set) var checkout: String?
    /// Labels of projects hidden from the app. Hiding touches nothing on disk; the loop, plist and repo stay as they are.
    public private(set) var hidden: Set<String>
    /// Projects found but hidden, so the menu can offer them back.
    public private(set) var hiddenProjects: [Project] = []

    public static let checkoutKey = "dcDevPluginsCheckout"
    public static let knownReposKey = "knownRepos"
    public static let knownScriptKey = "knownRunwayScript"
    public static let hiddenKey = "hiddenProjects"

    @ObservationIgnored private let discovery: ProjectDiscovery
    @ObservationIgnored private let interval: TimeInterval
    @ObservationIgnored private let defaults: UserDefaults
    @ObservationIgnored private let pauseURL: URL
    @ObservationIgnored private let run: (Command) async -> CommandResult
    @ObservationIgnored private let pidAlive: (Int) -> Bool
    @ObservationIgnored private var timer: Timer?
    @ObservationIgnored private var watchers: [String: DispatchSourceFileSystemObject] = [:]
    @ObservationIgnored private var snapshots: [String: StatusSnapshot] = [:]
    @ObservationIgnored private var ledger: NotificationLedger
    @ObservationIgnored private let ledgerURL: URL
    @ObservationIgnored private let machineURL: URL
    @ObservationIgnored private let deliver: (([NotificationEvent]) -> Void)?
    @ObservationIgnored private var waitingFetchedAt: Date = .distantPast
    @ObservationIgnored private var fetchingWaiting = false

    public init(discovery: ProjectDiscovery = ProjectDiscovery(), interval: TimeInterval = 5,
                defaults: UserDefaults = .standard, pauseURL: URL = PauseInfo.defaultURL,
                run: @escaping (Command) async -> CommandResult = { await CommandRunner.run($0) },
                pidAlive: @escaping (Int) -> Bool = StatusResolver.systemPidAlive,
                ledgerURL: URL = NotificationLedger.defaultURL, machineURL: URL = QuietHours.defaultURL,
                deliver: (([NotificationEvent]) -> Void)? = nil) {
        self.discovery = discovery
        self.interval = interval
        self.defaults = defaults
        self.pauseURL = pauseURL
        self.run = run
        self.pidAlive = pidAlive
        self.ledgerURL = ledgerURL
        self.machineURL = machineURL
        self.deliver = deliver
        self.ledger = deliver == nil ? NotificationLedger() : NotificationLedger.load(from: ledgerURL)
        self.checkout = defaults.string(forKey: Self.checkoutKey)
        self.hidden = Set(defaults.stringArray(forKey: Self.hiddenKey) ?? [])
    }

    public func hide(_ label: String) { setHidden(hidden.union([label])) }
    public func unhide(_ label: String) { setHidden(hidden.subtracting([label])) }

    private func setHidden(_ labels: Set<String>) {
        hidden = labels
        defaults.set(labels.sorted(), forKey: Self.hiddenKey)
        refresh()
    }

    public var tools: RunwayTools? { RunwayTools.locate(checkoutSetting: checkout, projects: projects) }

    public func start() {
        guard timer == nil else { return }
        refresh()
        timer = Timer.scheduledTimer(withTimeInterval: interval, repeats: true) { [weak self] _ in
            Task { @MainActor in self?.refresh() }
        }
    }

    public func stop() {
        timer?.invalidate()
        timer = nil
        watchers.values.forEach { $0.cancel() }
        watchers = [:]
    }

    public func refresh() {
        var found = discovery.discover()
        remember(found)
        found += stoppedProjects(besides: found)
        let shelved = found.filter { hidden.contains($0.label) }
        if shelved != hiddenProjects { hiddenProjects = shelved }
        found.removeAll { hidden.contains($0.label) }
        if found != projects { projects = found }

        let now = Date()
        let pause = PauseInfo.load(pauseURL, now: now)
        let newEntries = found.map { project -> ProjectEntry in
            let heartbeat = project.repoPath.flatMap { Heartbeat.load(repoPath: $0) }
            let status = StatusResolver.resolve(project: project, heartbeat: heartbeat, pause: pause,
                                                waiting: project.loaded ? snapshots[project.label]?.tickets.count ?? 0 : 0,
                                                now: now, pidAlive: pidAlive)
            return ProjectEntry(project: project, status: status)
        }
        if newEntries != entries { entries = newEntries }
        if pause != self.pause { self.pause = pause }
        let statuses = newEntries.map(\.status)
        overall = OverallState.resolve(statuses, pause: pause, now: now)
        badge = OverallState.badge(statuses)
        let planned = found.map { ProjectSnapshot(label: $0.label, name: $0.name, loopOn: $0.loaded, status: snapshots[$0.label]) }
        readyWhileOff = ProjectSnapshot.readyWhileOff(planned)
        notify(planned, now: now)
        updateWatchers(for: found)
        if now.timeIntervalSince(waitingFetchedAt) > 60 { refreshWaiting() }
    }

    // MARK: commands

    public func startLoop(_ project: Project) async {
        guard let repo = project.repoPath, let tools = requireTools() else { return }
        let minutes = max(1, (project.interval ?? 600) / 60)
        await perform(tools.start(repo: repo, minutes: minutes), "Start \(project.name)")
    }

    public func stopLoop(_ project: Project) async {
        guard let repo = project.repoPath, let tools = requireTools() else { return }
        await perform(tools.stop(repo: repo), "Stop \(project.name)")
    }

    public func runNow(_ project: Project) async {
        await perform(RunwayTools.runNow(label: project.label), "Run \(project.name) now")
    }

    public func pauseAll(_ choice: PauseChoice) async {
        guard let tools = requireTools() else { return }
        await perform(tools.pause(choice), "Pause")
    }

    public func resume() async {
        guard let tools = requireTools() else { return }
        await perform(tools.resume(), "Resume")
    }

    public func dismissError() { lastError = nil }

    /// The last `runway status --json` answer for a project; nil before the first one (or if every call failed).
    public func snapshot(for label: String) -> StatusSnapshot? { snapshots[label] }

    public func setCheckout(_ path: String?) {
        let value = path.flatMap { $0.isEmpty ? nil : $0 }
        checkout = value
        defaults.set(value, forKey: Self.checkoutKey)
    }

    private func requireTools() -> RunwayTools? {
        if let tools { return tools }
        lastError = "Can't find schedule.sh and runway.py. Choose the dc-dev-plugins checkout under Scripts."
        return nil
    }

    private func perform(_ command: Command, _ what: String) async {
        let result = await run(command)
        lastError = result.succeeded ? nil : "\(what) failed: \(result.failureMessage)"
        waitingFetchedAt = .distantPast
        refresh()
    }

    // MARK: stopped loops

    /// `schedule.sh uninstall` deletes the plist, so a stopped loop is remembered here to keep its Start button.
    private func remember(_ found: [Project]) {
        var known = knownRepos
        for project in found where project.error == nil {
            if let repo = project.repoPath { known[repo] = project.interval ?? known[repo] ?? 600 }
        }
        if known != knownRepos { defaults.set(known, forKey: Self.knownReposKey) }
        if let script = found.lazy.compactMap(\.runwayScript).first, script != knownScript {
            defaults.set(script, forKey: Self.knownScriptKey)
        }
    }

    private var knownScript: String? { defaults.string(forKey: Self.knownScriptKey) }

    private var knownRepos: [String: Int] {
        (defaults.dictionary(forKey: Self.knownReposKey) as? [String: Int]) ?? [:]
    }

    private func stoppedProjects(besides found: [Project]) -> [Project] {
        let present = Set(found.compactMap(\.repoPath))
        let script = found.lazy.compactMap(\.runwayScript).first ?? knownScript
        return knownRepos
            .filter { !present.contains($0.key) }
            .sorted { $0.key < $1.key }
            .map { discovery.stoppedProject(repoPath: $0.key, interval: $0.value, runwayScript: script) }
    }

    // MARK: notifications

    /// Plans from the latest snapshots, saves the ledger first, then delivers. A failed save means no delivery,
    /// so a restart can't repeat what was already shown.
    private func notify(_ planned: [ProjectSnapshot], now: Date) {
        guard let deliver else { return }
        let result = NotificationPlanner.plan(planned, ledger: ledger, now: now, quiet: QuietHours.load(machineURL))
        guard result.ledger != ledger else { return }
        do { try result.ledger.save(to: ledgerURL) } catch { return }
        ledger = result.ledger
        if !result.events.isEmpty { deliver(result.events) }
    }

    // MARK: decisions waiting

    /// Asks `runway status --json` what waits and what is ready in each project, loop on or off. It can hit a tracker over the
    /// network, so it runs off the main thread at most once a minute and keeps the last answer if a call fails.
    private func refreshWaiting() {
        guard !fetchingWaiting, let tools else { return }
        fetchingWaiting = true
        waitingFetchedAt = Date()
        let targets = projects.compactMap { project -> (String, String)? in
            guard project.error == nil, let repo = project.repoPath else { return nil }
            return (project.label, repo)
        }
        Task {
            var changed = false
            for (label, repo) in targets {
                let result = await run(tools.status(repo: repo))
                guard result.succeeded,
                      let snapshot = StatusSnapshot.parse(Data(result.stdout.utf8)) else { continue }
                if snapshots[label] != snapshot {
                    snapshots[label] = snapshot
                    changed = true
                }
            }
            fetchingWaiting = false
            if changed { refresh() }
        }
    }

    private func updateWatchers(for projects: [Project]) {
        let wanted = Set(projects.compactMap { $0.error == nil && $0.loaded ? $0.repoPath : nil })
        for (path, source) in watchers where !wanted.contains(path) {
            source.cancel()
            watchers[path] = nil
        }
        for repo in wanted where watchers[repo] == nil {
            let fd = open(repo + "/_pm", O_EVTONLY)
            guard fd >= 0 else { continue }
            let source = DispatchSource.makeFileSystemObjectSource(
                fileDescriptor: fd, eventMask: [.write, .rename, .delete, .extend], queue: .main)
            source.setEventHandler { [weak self] in
                Task { @MainActor in self?.refresh() }
            }
            source.setCancelHandler { close(fd) }
            source.resume()
            watchers[repo] = source
        }
    }
}
