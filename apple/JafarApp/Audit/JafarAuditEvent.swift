import Foundation

struct JafarAuditEvent: Codable, Sendable, Identifiable {
    let id: UUID
    let action: String
    let entityType: String
    let entityID: UUID?
    let oldPayload: [String: String]?
    let newPayload: [String: String]?
    let deviceID: String?
    let source: String
    let confirmed: Bool
    let occurredAt: Date
}

protocol JafarAuditLogging: AnyObject {
    func record(_ event: JafarAuditEvent) async throws
}
