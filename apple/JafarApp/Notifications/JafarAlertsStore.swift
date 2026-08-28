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
    static let shared = JafarAlertsStore()

    @Published private(set) var alerts: [JafarAlert] = []
    private var dismissedIDs: Set<String> = []

    var urgentCount: Int {
        alerts.count { $0.priority >= 80 }
    }

    var approvalCount: Int {
        alerts.count { $0.requiresApproval }
    }

    func replace(with newAlerts: [JafarAlert]) {
        alerts = newAlerts
            .filter { !dismissedIDs.contains($0.id) }
            .sorted(by: Self.order)
    }

    func replace(with signals: [DashboardSignal], generatedAt: String) {
        let timestamp = ISO8601DateFormatter().date(from: generatedAt) ?? Date()
        replace(
            with: signals.map { signal in
                JafarAlert(
                    id: signal.id,
                    title: signal.title,
                    body: signal.body,
                    priority: signal.priority,
                    requiresApproval: signal.requiresApproval,
                    createdAt: timestamp
                )
            }
        )
    }

    func add(_ alert: JafarAlert) {
        guard !dismissedIDs.contains(alert.id) else { return }
        alerts.removeAll { $0.id == alert.id }
        alerts.append(alert)
        alerts.sort(by: Self.order)
    }

    func dismiss(_ id: String) {
        dismissedIDs.insert(id)
        alerts.removeAll { $0.id == id }
    }

    private static func order(_ left: JafarAlert, _ right: JafarAlert) -> Bool {
        if left.priority != right.priority {
            return left.priority > right.priority
        }
        return left.createdAt > right.createdAt
    }
}
