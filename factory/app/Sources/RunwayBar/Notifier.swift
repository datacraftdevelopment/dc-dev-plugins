import AppKit
import UserNotifications
import RunwayCore

/// Delivers `NotificationEvent`s through UserNotifications and routes a click back to the store.
/// Needs a bundled app (`make-app.sh`); an unbundled `swift run` has no notification center, so this stays quiet there.
@MainActor
final class Notifier: NSObject, UNUserNotificationCenterDelegate {
    private let store: ProjectStore
    private var center: UNUserNotificationCenter? {
        Bundle.main.bundleIdentifier == nil ? nil : UNUserNotificationCenter.current()
    }

    init(store: ProjectStore) {
        self.store = store
        super.init()
        guard let center else { return }
        center.delegate = self
        center.requestAuthorization(options: [.alert, .sound]) { _, _ in }
    }

    func deliver(_ events: [NotificationEvent]) {
        guard let center else { return }
        for event in events {
            let content = UNMutableNotificationContent()
            content.title = event.title
            content.body = event.body
            content.userInfo = event.userInfo
            center.add(UNNotificationRequest(identifier: event.identifier, content: content, trigger: nil))
        }
    }

    nonisolated func userNotificationCenter(_ center: UNUserNotificationCenter, willPresent notification: UNNotification,
                                            withCompletionHandler handler: @escaping (UNNotificationPresentationOptions) -> Void) {
        handler([.banner, .sound])
    }

    nonisolated func userNotificationCenter(_ center: UNUserNotificationCenter, didReceive response: UNNotificationResponse,
                                            withCompletionHandler handler: @escaping () -> Void) {
        let route = NotificationRoute(userInfo: response.notification.request.content.userInfo)
        Task { @MainActor in
            if let route {
                self.store.requestedRoute = route
                NSApplication.shared.activate(ignoringOtherApps: true)
            }
            handler()
        }
    }
}
