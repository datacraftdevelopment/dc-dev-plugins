import Foundation
import Sparkle
import RunwayCore

/// Owns Sparkle. With no `SUPublicEDKey` in Info.plist the controller is never created, so a build
/// without a signing key can't check for or accept an update.
@MainActor
final class AppUpdater {
    let state: UpdaterState
    private let controller: SPUStandardUpdaterController?

    init(bundle: Bundle = .main) {
        let key = bundle.object(forInfoDictionaryKey: "SUPublicEDKey") as? String
        state = UpdaterState.decide(publicKey: key)
        // Sparkle checks once a day on its own (SUEnableAutomaticChecks and SUScheduledCheckInterval in Info.plist).
        controller = state == .on
            ? SPUStandardUpdaterController(startingUpdater: true, updaterDelegate: nil, userDriverDelegate: nil)
            : nil
    }

    func checkForUpdates() { controller?.checkForUpdates(nil) }
}
