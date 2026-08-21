import Foundation
import UserNotifications

@MainActor
final class DeadlineNotificationScheduler {
    func requestPermission() async -> Bool {
        do {
            return try await UNUserNotificationCenter.current()
                .requestAuthorization(options: [.alert, .sound, .badge])
        } catch {
            return false
        }
    }

    func schedule(
        id: String,
        title: String,
        body: String,
        dueAt: Date,
        reminderOffsets: [TimeInterval] = [7 * 24 * 3600, 2 * 24 * 3600, 24 * 3600]
    ) async throws {
        let center = UNUserNotificationCenter.current()
        for (index, offset) in reminderOffsets.enumerated() {
            let fireDate = dueAt.addingTimeInterval(-offset)
            guard fireDate > Date() else { continue }

            var components = Calendar.current.dateComponents(
                [.year, .month, .day, .hour, .minute],
                from: fireDate
            )
            components.timeZone = .current

            let content = UNMutableNotificationContent()
            content.title = title
            content.body = body
            content.sound = .default

            let trigger = UNCalendarNotificationTrigger(dateMatching: components, repeats: false)
            let request = UNNotificationRequest(
                identifier: "jafar.deadline.\(id).\(index)",
                content: content,
                trigger: trigger
            )
            try await center.add(request)
        }
    }
}
