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
    /// Tools this Mac needs signed in again (from the loops' sign-in checks and a sign-in pause), first in Needs you.
    public private(set) var signInNeeds: [SignInNeed] = []
    /// What the last sign-in re-check found, shown beside the sign-in rows until the next sign-in starts.
    public private(set) var signInNote: String?
    /// True while the re-check after a sign-in session runs.
    public private(set) var signInChecking = false
    /// What each chore's last run ended with, by its session key, shown beside its button.
    public private(set) var choreResults: [String: String] = [:]
    @ObservationIgnored private var runningChores: [String: (Chore, String?)] = [:]
    /// A project has ready tickets but its loop is off. Drives the amber icon; independent of notifications.
    public private(set) var readyWhileOff = false
    /// Set when a notification is clicked: the tab the window should open on.
    public var requestedRoute: NotificationRoute?
    /// The last command's stderr when it failed; cleared by the next success or `dismissError()`.
    public private(set) var lastError: String?
    /// Failed "Talk it through" launches, by project and ticket, so the error sits beside its button.
    private var talkErrors: [String: String] = [:]
    /// Failed Start/Stop commands by project label (shown in the window and the side panel), and the projects whose command is running now.
    private var loopErrors: [String: String] = [:]
    private var loopBusy: Set<String> = []
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
    public static let sessionPlaceKey = "sessionPlace"

    /// The Claude sessions "Talk it through" opened in the Runway window's terminal pane.
    public let sessions = SessionRegistry()
    /// Where "Talk it through" opens its session.
    public private(set) var sessionPlace: SessionPlace

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

    /// The heartbeat if its tick is really running (active phase, pid alive), else nil.
    public func live(_ heartbeat: Heartbeat?) -> Heartbeat? {
        heartbeat.flatMap { $0.isLive(pidAlive: pidAlive) ? $0 : nil }
    }

    /// "Loop stopped during check · 17:18" when the heartbeat is a dead tick.
    public func stoppedLine(_ heartbeat: Heartbeat?) -> String? {
        heartbeat?.stoppedDescription(pidAlive: pidAlive)
    }

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
        self.sessionPlace = defaults.string(forKey: Self.sessionPlaceKey).flatMap(SessionPlace.init(rawValue:)) ?? .window
        sessions.onExit = { [weak self] session in
            guard let self, let key = session.command?.key else { return }
            if key.hasPrefix("signin:") { Task { await self.recheckSignIns() } }
            if key.hasPrefix("chore:") { Task { await self.choreEnded(key, exit: session.exitCode) } }
        }
    }

    public func setSessionPlace(_ place: SessionPlace) {
        sessionPlace = place
        defaults.set(place.rawValue, forKey: Self.sessionPlaceKey)
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
                                                errored: project.loaded ? snapshots[project.label]?.erroredOnlyCount ?? 0 : 0,
                                                now: now, pidAlive: pidAlive)
            return ProjectEntry(project: project, status: status)
        }
        if newEntries != entries { entries = newEntries }
        if pause != self.pause { self.pause = pause }
        let statuses = newEntries.map(\.status)
        let needs = SignInNeed.resolve(found.compactMap { snapshots[$0.label] }, pause: pause)
        if needs != signInNeeds { signInNeeds = needs }
        let resolved = OverallState.resolve(statuses, pause: pause, now: now)
        overall = needs.isEmpty || resolved == .allOff || resolved == .error ? resolved : .waiting
        badge = OverallState.badge(statuses) + needs.count
        let planned = found.map { ProjectSnapshot(label: $0.label, name: $0.name, loopOn: $0.loaded, status: snapshots[$0.label]) }
        readyWhileOff = ProjectSnapshot.readyWhileOff(planned)
        notify(planned, now: now)
        updateWatchers(for: found)
        if now.timeIntervalSince(waitingFetchedAt) > 60 { refreshWaiting() }
    }

    // MARK: commands

    public func startLoop(_ project: Project) async {
        guard let repo = project.repoPath, !loopBusy.contains(project.label) else { return }
        guard let tools = requireTools() else { loopErrors[project.label] = lastError; return }
        let minutes = max(1, (project.interval ?? 600) / 60)
        await performLoop(project, tools.start(repo: repo, minutes: minutes), "Start \(project.name)")
    }

    /// Why the last Start (or Stop) for this project failed; nil after one that worked. Same store as `loopError(for:)`.
    public func startError(project: Project) -> String? { loopErrors[project.label] }

    public func stopLoop(_ project: Project) async {
        guard let repo = project.repoPath, !loopBusy.contains(project.label) else { return }
        guard let tools = requireTools() else { loopErrors[project.label] = lastError; return }
        await performLoop(project, tools.stop(repo: repo), "Stop \(project.name)")
    }

    /// True while this project's Start or Stop command runs, so the panel can show a spinner and ignore a second press.
    public func isLoopBusy(_ project: Project) -> Bool { loopBusy.contains(project.label) }

    /// Why this project's last Start or Stop failed; nil after one that worked or after `dismissLoopError`.
    public func loopError(for project: Project) -> String? { loopErrors[project.label] }

    public func dismissLoopError(for project: Project) { loopErrors[project.label] = nil }

    private func performLoop(_ project: Project, _ command: Command, _ what: String) async {
        loopBusy.insert(project.label)
        defer { loopBusy.remove(project.label) }
        await perform(command, what)
        loopErrors[project.label] = lastError
    }

    public func runNow(_ project: Project) async {
        await perform(RunwayTools.runNow(label: project.label), "Run \(project.name) now")
    }

    public func pauseAll(_ choice: PauseChoice) async {
        guard let tools = requireTools() else { return }
        let mode = (try? MachineStore().load().pauseMode) ?? .finish  // the This Mac sheet's pause_mode
        await perform(tools.pause(choice, mode: mode), "Pause")
    }

    public func resume() async {
        guard let tools = requireTools() else { return }
        await perform(tools.resume(), "Resume")
    }

    public func dismissError() { lastError = nil }

    // MARK: talk it through

    /// Opens Terminal on `runway discuss <ticket>` for the project.
    public func talkThrough(ticket: String, in project: Project) async {
        guard let repo = project.repoPath, let tools = requireTools() else { return }
        if sessionPlace == .window {
            sessions.open(project: project.label, ticket: ticket, spec: tools.discussSession(ticket: ticket, repo: repo))
            return
        }
        await launch(tools.discuss(ticket: ticket, repo: repo), key: Self.talkKey(project, ticket))
    }

    /// Opens the ticket's own worker conversation (`runway discuss <ticket> --resume`), in the pane or Terminal.
    public func resumeWorker(ticket: String, in project: Project) async {
        guard let repo = project.repoPath, let tools = requireTools() else { return }
        if sessionPlace == .window {
            sessions.open(project: project.label, ticket: ticket, resume: true,
                          spec: tools.discussResumeSession(ticket: ticket, repo: repo))
            return
        }
        await launch(tools.discussResume(ticket: ticket, repo: repo), key: Self.talkKey(project, ticket, resume: true))
    }

    /// Opens the last finish review's own conversation (`runway discuss --review`), in the pane or Terminal.
    /// `reviewSession` is status's `review_session`: a pane still open on an older review gets a new tab beside it.
    public func openLastReview(_ project: Project, reviewSession: String?) async {
        guard let repo = project.repoPath, let tools = requireTools() else { return }
        if sessionPlace == .window {
            sessions.open(project: project.label, ticket: nil, resume: true, reviewSession: reviewSession,
                          spec: tools.discussReviewSession(repo: repo, session: reviewSession))
            return
        }
        await launch(tools.discussReview(repo: repo, session: reviewSession), key: Self.talkKey(project, nil, resume: true))
    }

    /// Opens Terminal on `runway discuss --loop` for the project.
    public func talkThroughLoop(_ project: Project) async {
        guard let repo = project.repoPath, let tools = requireTools() else { return }
        if sessionPlace == .window {
            sessions.open(project: project.label, ticket: nil, spec: tools.discussLoopSession(repo: repo))
            return
        }
        await launch(tools.discussLoop(repo: repo), key: Self.talkKey(project, nil))
    }

    // MARK: sign-in

    /// Runs the need's fix command in the window's pane (always the pane: its exit starts the re-check).
    public func signIn(_ need: SignInNeed) {
        guard let spec = need.session(), let fix = need.fix else { return }
        signInNote = nil
        sessions.open(command: CommandSession(key: need.sessionKey, title: "Sign in: \(need.label)", line: fix), spec: spec)
    }

    /// After a sign-in session ends: `runway signin` in every project, then, when all pass, lift a sign-in pause
    /// and run a tick now for each loop that was waiting on it. The result shows beside the sign-in rows.
    public func recheckSignIns() async {
        guard let tools = requireTools(), !signInChecking else { return }
        signInChecking = true
        defer { signInChecking = false }
        var failing: [SignInCheck] = []
        var allPassed = true
        for project in projects where project.error == nil {
            guard let repo = project.repoPath else { continue }
            let result = await run(tools.signin(repo: repo))
            let checks = (try? JSONSerialization.jsonObject(with: Data(result.stdout.utf8))).map(SignInCheck.parse) ?? []
            if !result.succeeded {
                allPassed = false
                let bad = checks.filter { !$0.ok }
                if bad.isEmpty { failing.append(SignInCheck(name: "signin", label: project.name, fix: nil, ok: false,
                                                            detail: "\(project.name): sign-in check failed: \(result.failureMessage)")) }
                failing += bad.filter { b in !failing.contains { $0.name == b.name } }
            }
        }
        let pauseReason = PauseInfo.load(pauseURL)?.reason
        let waiting = projects.filter {
            $0.loaded && SignInFollowUp.wasWaiting($0.repoPath.flatMap { Heartbeat.load(repoPath: $0) }, pauseReason: pauseReason)
        }
        // In order, stopping at the first failure: no tick is kicked if the sign-in pause couldn't be lifted.
        for command in SignInFollowUp.commands(allPassed: allPassed, tools: tools, waitingLoops: waiting.map(\.label)) {
            let result = await run(command)
            if !result.succeeded {
                failing.append(SignInCheck(name: "follow-up", label: "", fix: nil, ok: false, detail: result.failureMessage))
                break
            }
        }
        let labels = signInNeeds.map(\.label).joined(separator: ", ")
        signInNote = SignInFollowUp.note(label: labels.isEmpty ? "Sign-in" : labels, failing: failing)
        waitingFetchedAt = .distantPast
        refresh()
    }

    // MARK: chores

    /// The engine checkout the chores list and its commands come from.
    public var engineCheckout: String? {
        checkout ?? tools.map { SetupChecks.checkout(ofRunwayScript: $0.runwayScript) }
    }

    public func choreList() -> ChoreList {
        guard let engineCheckout else { return .unusable("Can't find the engine checkout. Choose it under Scripts.") }
        return ChoreList.load(checkout: engineCheckout)
    }

    /// The chores for one place whose `show_if` passes now (each at most 10 seconds). `repo` for per-repo chores.
    public func visibleChores(_ place: Chore.Place, repo: String? = nil) async -> [Chore] {
        guard let engineCheckout else { return [] }
        var shown: [Chore] = []
        for chore in choreList().chores where chore.cwd == place {
            guard let check = chore.showIfCommand(checkout: engineCheckout, repo: repo) else { shown.append(chore); continue }
            if Chore.needed(probe: await run(check)) { shown.append(chore) }
        }
        return shown
    }

    /// The exact line a chore runs and where, for the button to show before the click.
    public func choreLine(_ chore: Chore, repo: String? = nil) -> String? {
        guard let tools, let engineCheckout, let folder = chore.folder(checkout: engineCheckout, repo: repo) else { return nil }
        return "cd \(RunwayTools.shellQuote(folder)) && " + chore.line(runwayScript: tools.runwayScript, checkout: engineCheckout, repo: repo)
    }

    /// Runs the chore in the window's pane, as Joe. Its exit re-runs `show_if` and records the result.
    public func runChore(_ chore: Chore, repo: String? = nil) {
        guard let tools, let engineCheckout, let line = choreLine(chore, repo: repo),
              let spec = chore.session(runwayScript: tools.runwayScript, checkout: engineCheckout, repo: repo) else { return }
        let key = chore.sessionKey(repo: repo)
        choreResults[key] = nil
        runningChores[key] = (chore, repo)
        sessions.open(command: CommandSession(key: key, title: chore.title, line: line), spec: spec)
    }

    public func choreResult(_ chore: Chore, repo: String? = nil) -> String? { choreResults[chore.sessionKey(repo: repo)] }

    private func choreEnded(_ key: String, exit: Int32?) async {
        guard let pending = runningChores.removeValue(forKey: key) else { return }
        let (chore, repo) = pending
        var probe: CommandResult?
        if exit == 0, let engineCheckout, let check = chore.showIfCommand(checkout: engineCheckout, repo: repo) {
            probe = await run(check)
        }
        choreResults[key] = chore.result(exit: exit, probe: probe)
    }

    /// Ends the pane's session (the view has already asked) and reopens the same discussion in Terminal.
    public func popOut(_ id: UUID) async {
        guard let session = sessions.sessions.first(where: { $0.id == id }), let tools = requireTools() else { return }
        let repo = session.spec.workingDirectory
        sessions.close(id)
        if let line = session.command?.line {
            let result = await run(RunwayTools.terminal(line: line))
            if !result.succeeded { lastError = result.failureMessage }
            return
        }
        let command = session.ticket.map {
            session.resume ? tools.discussResume(ticket: $0, repo: repo) : tools.discuss(ticket: $0, repo: repo)
        } ?? (session.resume ? tools.discussReview(repo: repo, session: session.reviewSession) : tools.discussLoop(repo: repo))
        let result = await run(command)
        if !result.succeeded { lastError = result.failureMessage }
    }

    /// Why the last launch for this ticket (or the loop, with nil) failed; nil after a launch that worked.
    public func talkError(project: Project, ticket: String?, resume: Bool = false) -> String? {
        talkErrors[Self.talkKey(project, ticket, resume: resume)]
    }

    private static func talkKey(_ project: Project, _ ticket: String?, resume: Bool = false) -> String {
        project.label + "/" + (ticket ?? "") + (resume ? "#resume" : "")
    }

    private func launch(_ command: Command, key: String) async {
        let result = await run(command)
        talkErrors[key] = result.succeeded ? nil : result.failureMessage
    }

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
