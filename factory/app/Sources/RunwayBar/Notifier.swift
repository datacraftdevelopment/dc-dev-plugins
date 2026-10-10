import AppKit
import UserNotifications
import RunwayCore

/// Delivers `NotificationEvent`s through UserNotifications and routes a click back to the store.
/// Needs a bundled app (`make-app.sh`); an unbundled `swift run` has no notification center, so this stays quiet there.
@MainActor
final class Notifier: NSObject, UNUserNotificationCenterDelegate {
    private nonisolated static let talkCategory = "runway.talk"
    private nonisolated static let talkAction = "runway.talk.action"
    private let store: ProjectStore
    private var center: UNUserNotificationCenter? {
        Bundle.main.bundleIdentifier == nil ? nil : UNUserNotificationCenter.current()
    }

    init(store: ProjectStore) {
        self.store = store
        super.init()
        guard let center else { return }
        center.delegate = self
        // A decision or parked ticket gets a "Talk it through" action; the plain click still opens the Decisions tab.
        center.setNotificationCategories([UNNotificationCategory(
            identifier: Self.talkCategory, actions: [UNNotificationAction(identifier: Self.talkAction, title: "Talk it through")],
            intentIdentifiers: [])])
        center.requestAuthorization(options: [.alert, .sound]) { _, _ in }
    }

    func deliver(_ events: [NotificationEvent]) {
        guard let center else { return }
        for event in events {
            let content = UNMutableNotificationContent()
            content.title = event.title
            content.body = event.body
            content.userInfo = event.userInfo
            if event.kind != .idleReady, event.ticketID != nil { content.categoryIdentifier = Self.talkCategory }
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
        let talk = response.actionIdentifier == Self.talkAction
        Task { @MainActor in
            if talk, let route, let ticket = route.ticketID,
               let project = self.store.projects.first(where: { $0.label == route.projectLabel }) {
                await self.store.talkThrough(ticket: ticket, in: project)
                if self.store.sessionPlace == .window { NSApplication.shared.activate(ignoringOtherApps: true) }
            } else if let route {
                self.store.requestedRoute = route
                NSApplication.shared.activate(ignoringOtherApps: true)
            }
            handler()
        }
    }
}
