import Foundation

/// Whether the app may check for updates. Sparkle only runs when the build carries a public key,
/// so a build without one never accepts an unsigned update and never crashes looking for a key.
public enum UpdaterState: Equatable {
    case on
    case off

    /// `publicKey` is `SUPublicEDKey` from Info.plist; `make-app.sh` omits it when there's no key file.
    public static func decide(publicKey: String?) -> UpdaterState {
        guard let key = publicKey?.trimmingCharacters(in: .whitespacesAndNewlines), !key.isEmpty else { return .off }
        return .on
    }

    /// The menu line shown instead of "Check for Updates…" when the updater is off.
    public var menuNote: String? {
        self == .off ? "Updates off: no signing key" : nil
    }
}
