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

    func add(_ alert: JafarAlert) {
        alerts.append(alert)
        alerts.sort { $0.priority > $1.priority }
    }

    func dismiss(_ id: String) {
        alerts.removeAll { $0.id == id }
    }
}
