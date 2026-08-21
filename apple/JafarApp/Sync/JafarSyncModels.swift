import Foundation

struct SyncEnvelope: Codable, Sendable, Equatable {
    let deviceId: String
    let userId: String
    let entityType: String
    let entityId: String
    let version: Int64
    let operation: String
    let payload: Data
    let updatedAt: Date
    let requiresLegalReview: Bool
}

struct SyncChange: Codable, Sendable {
    let entity: SyncEnvelope
}

actor JafarSyncCoordinator {
    private var versions: [String: Int64] = [:]

    func accept(_ change: SyncChange) -> Bool {
        let key = "\(change.entity.entityType):\(change.entity.entityId)"
        let current = versions[key, default: 0]
        guard change.entity.version > current else { return false }
        versions[key] = change.entity.version
        return true
    }
}
