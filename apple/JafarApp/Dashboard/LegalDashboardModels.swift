import Foundation

struct LegalDashboardItem: Identifiable, Sendable {
    enum Kind: Sendable { case task, deadline, risk }
    let id: String
    let kind: Kind
    let title: String
    let subtitle: String
    let dueAt: Date?
    let confidence: Double
    let requiresApproval: Bool
}

struct LegalDashboardSnapshot: Sendable {
    let items: [LegalDashboardItem]
    let generatedAt: Date
}
