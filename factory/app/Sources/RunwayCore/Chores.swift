import Foundation

/// One entry of the engine checkout's `pm/runway/chores.json`: a machine chore the app offers as a button.
/// The file is data; the app runs the listed command and nothing else (field meanings in `pm/runway/chores.md`).
public struct Chore: Equatable, Sendable, Identifiable {
    public enum Place: String, Equatable, Sendable { case checkout, repo }

    public let id: String
    public let title: String
    public let why: String
    public let run: String
    public let cwd: Place
    public let showIf: String?
    public let confirm: Bool

    public init(id: String, title: String, why: String, run: String, cwd: Place, showIf: String? = nil, confirm: Bool = false) {
        self.id = id
        self.title = title
        self.why = why
        self.run = run
        self.cwd = cwd
        self.showIf = showIf
        self.confirm = confirm
    }

    /// The shell line with `{runway}`, `{repo}` and `{checkout}` replaced by their shell-quoted paths.
    public func line(runwayScript: String, checkout: String, repo: String?) -> String {
        var text = run.replacingOccurrences(of: "{runway}", with: RunwayTools.shellQuote(runwayScript))
            .replacingOccurrences(of: "{checkout}", with: RunwayTools.shellQuote(checkout))
        if let repo { text = text.replacingOccurrences(of: "{repo}", with: RunwayTools.shellQuote(repo)) }
        return text
    }

    /// The folder it runs in: the engine checkout, or the loop's repo for a per-repo chore.
    public func folder(checkout: String, repo: String?) -> String? {
        cwd == .checkout ? checkout : repo
    }

    /// What the pane runs: the line through a login shell, in its folder.
    public func session(runwayScript: String, checkout: String, repo: String?) -> LaunchSpec? {
        guard let folder = folder(checkout: checkout, repo: repo) else { return nil }
        return LaunchSpec(executable: "/bin/zsh", arguments: ["-lc", line(runwayScript: runwayScript, checkout: checkout, repo: repo)],
                          workingDirectory: folder)
    }

    /// `show_if` as a command with a 10 second limit (perl's alarm: macOS has no `timeout`), run in the chore's folder.
    /// nil when the chore has no `show_if` (always shown).
    public func showIfCommand(checkout: String, repo: String?) -> Command? {
        guard let showIf, let folder = folder(checkout: checkout, repo: repo) else { return nil }
        return Command(executable: "/usr/bin/perl", arguments: [
            "-e", "alarm shift; exec @ARGV", "10", "/bin/zsh", "-lc", "cd \(RunwayTools.shellQuote(folder)) && \(showIf)"])
    }

    /// One pane tab per chore (and per repo for a per-repo chore).
    public func sessionKey(repo: String?) -> String {
        "chore:\(id)" + (cwd == .repo ? ":\(repo ?? "")" : "")
    }
}

/// `chores.json`, read: the chores, or why the file can't be used.
public enum ChoreList: Equatable, Sendable {
    case chores([Chore])
    case unusable(String)

    public static func path(checkout: String) -> String {
        URL(fileURLWithPath: checkout).appendingPathComponent("pm/runway/chores.json").path
    }

    public static func load(checkout: String) -> ChoreList {
        guard let data = FileManager.default.contents(atPath: path(checkout: checkout)) else {
            return .unusable("No chores list in this checkout (pm/runway/chores.json). Update Runway to get it.")
        }
        return parse(data)
    }

    /// Version 1 only. An entry missing a field, or with an unknown `cwd`, is skipped rather than guessed at.
    public static func parse(_ data: Data) -> ChoreList {
        guard let json = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any] else {
            return .unusable("pm/runway/chores.json isn't valid JSON.")
        }
        guard (json["version"] as? Int) == 1 else {
            return .unusable("pm/runway/chores.json has a version this app doesn't know. Update Runway.")
        }
        let entries = (json["chores"] as? [[String: Any]]) ?? []
        return .chores(entries.compactMap { e in
            guard let id = e["id"] as? String, !id.isEmpty, let title = e["title"] as? String,
                  let run = e["run"] as? String, !run.isEmpty,
                  let cwd = (e["cwd"] as? String).flatMap(Chore.Place.init(rawValue:)) else { return nil }
            return Chore(id: id, title: title, why: (e["why"] as? String) ?? "", run: run, cwd: cwd,
                         showIf: (e["show_if"] as? String).flatMap { $0.isEmpty ? nil : $0 },
                         confirm: (e["confirm"] as? Bool) == true)
        })
    }

    public var chores: [Chore] { if case .chores(let list) = self { return list } else { return [] } }
}
