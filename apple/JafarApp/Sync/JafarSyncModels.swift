import Foundation

struct SyncEntity: Codable, Sendable, Hashable {
    let entityType: String
    let entityId: String
    let version: Int64
    let updatedAt: Date
}

struct SyncChange: Codable, Sendable {
    let entity: SyncEntity
    let operation: String
    let payload: [String: String]
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
