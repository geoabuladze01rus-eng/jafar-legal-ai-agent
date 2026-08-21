import Foundation
import UserNotifications

struct JafarDeadlineNotificationScheduler {
    func requestPermission() async throws -> Bool {
        try await UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .sound, .badge])
    }

    func schedule(
        deadlineID: String,
        title: String,
        dueAt: Date,
        leadHours: [Int] = [168, 72, 24]
    ) async throws {
        let center = UNUserNotificationCenter.current()
        for hours in leadHours {
            let fireDate = dueAt.addingTimeInterval(TimeInterval(-hours * 3600))
            guard fireDate > Date() else { continue }
            var components = Calendar.current.dateComponents([.year, .month, .day, .hour, .minute], from: fireDate)
            let content = UNMutableNotificationContent()
            content.title = "Джафар: приближается срок"
            content.body = "\(title) — осталось около \(hours) ч."
            content.sound = .default
            let trigger = UNCalendarNotificationTrigger(dateMatching: components, repeats: false)
            let request = UNNotificationRequest(identifier: "jafar-deadline-\(deadlineID)-\(hours)", content: content, trigger: trigger)
            try await center.add(request)
            components = DateComponents()
        }
    }

    func scheduleOverdueAlert(deadlineID: String, title: String, dueAt: Date) async throws {
        guard dueAt <= Date() else { return }
        let content = UNMutableNotificationContent()
        content.title = "Джафар: срок просрочен"
        content.body = title
        content.sound = .default
        let request = UNNotificationRequest(
            identifier: "jafar-deadline-overdue-\(deadlineID)",
            content: content,
            trigger: nil
        )
        try await UNUserNotificationCenter.current().add(request)
    }
}
