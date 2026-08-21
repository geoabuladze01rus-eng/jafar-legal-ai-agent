import Foundation

enum SyncConflictDecision: Sendable {
    case acceptRemote
    case keepLocal
    case requiresUserReview
}

struct SyncConflict: Sendable, Identifiable {
    let id: String
    let entityType: String
    let entityId: String
    let localVersion: Int64
    let remoteVersion: Int64
    let localUpdatedAt: Date
    let remoteUpdatedAt: Date
}

struct JafarConflictResolver {
    func decide(
        local: SyncEnvelope,
        remote: SyncEnvelope
    ) -> SyncConflictDecision {
        guard local.entityType == remote.entityType,
              local.entityId == remote.entityId else {
            return .requiresUserReview
        }

        // Legal matters and legal deadlines are never silently overwritten.
        if local.requiresLegalReview || remote.requiresLegalReview {
            if local.payload == remote.payload { return .keepLocal }
            return .requiresUserReview
        }

        if local.version > remote.version { return .keepLocal }
        if remote.version > local.version { return .acceptRemote }

        // Equal versions with different payloads are never silently overwritten.
        if local.payload == remote.payload { return .keepLocal }
        return .requiresUserReview
    }

    func conflict(local: SyncEnvelope, remote: SyncEnvelope) -> SyncConflict {
        SyncConflict(
            id: "\(local.entityType):\(local.entityId):\(local.version):\(remote.version)",
            entityType: local.entityType,
            entityId: local.entityId,
            localVersion: local.version,
            remoteVersion: remote.version,
            localUpdatedAt: local.updatedAt,
            remoteUpdatedAt: remote.updatedAt
        )
    }
}
