import Foundation

enum JafarAlertDelivery: Sendable {
    case dashboard
    case push
    case dashboardAndPush
}

struct JafarAlertDeliveryPolicy {
    func delivery(for item: JafarNotificationItem) -> JafarAlertDelivery {
        switch item.kind {
        case .overdue, .criticalRisk:
            return .dashboardAndPush
        case .deadline:
            return item.priority >= 90 ? .dashboardAndPush : .dashboard
        case .newLegalMail:
            return .dashboardAndPush
        case .approvalRequired:
            return .dashboardAndPush
        }
    }
}
