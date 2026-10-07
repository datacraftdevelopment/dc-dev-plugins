import Foundation
import Observation

/// Holds the discovered projects for the views. Refreshes on a timer and when anything in a repo's `_pm/` changes.
@MainActor
@Observable
public final class ProjectStore {
    public private(set) var projects: [Project] = []

    @ObservationIgnored private let discovery: ProjectDiscovery
    @ObservationIgnored private let interval: TimeInterval
    @ObservationIgnored private var timer: Timer?
    @ObservationIgnored private var watchers: [String: DispatchSourceFileSystemObject] = [:]

    public init(discovery: ProjectDiscovery = ProjectDiscovery(), interval: TimeInterval = 5) {
        self.discovery = discovery
        self.interval = interval
    }

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
        let found = discovery.discover()
        if found != projects { projects = found }
        updateWatchers(for: found)
    }

    private func updateWatchers(for projects: [Project]) {
        let wanted = Set(projects.compactMap { $0.error == nil ? $0.repoPath : nil })
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
