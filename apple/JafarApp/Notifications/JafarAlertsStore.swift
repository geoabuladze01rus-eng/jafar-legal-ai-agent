import Combine
import Foundation

struct JafarAlert: Identifiable, Sendable {
    let id: String
    let title: String
    let body: String
    let priority: Int
    let requiresApproval: Bool
    let createdAt: Date
}

@MainActor
final class JafarAlertsStore: ObservableObject {
    @Published private(set) var alerts: [JafarAlert] = []

    var urgentCount: Int {
        alerts.count { $0.priority >= 80 }
    }

    var approvalCount: Int {
        alerts.count { $0.requiresApproval }
    }

    func replace(with newAlerts: [JafarAlert]) {
        alerts = newAlerts.sorted(by: Self.order)
    }

    func add(_ alert: JafarAlert) {
        alerts.removeAll { $0.id == alert.id }
        alerts.append(alert)
        alerts.sort(by: Self.order)
    }

    func dismiss(_ id: String) {
        alerts.removeAll { $0.id == id }
    }

    private static func order(_ left: JafarAlert, _ right: JafarAlert) -> Bool {
        if left.priority != right.priority {
            return left.priority > right.priority
        }
        return left.createdAt > right.createdAt
    }
}
