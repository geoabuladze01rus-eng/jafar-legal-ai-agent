import Foundation

struct SyncEnvelope: Codable, Sendable {
    let deviceId: String
    let userId: String
    let entityType: String
    let entityId: String
    let version: Int64
    let operation: String
    let payload: Data
    let updatedAt: Date
}

actor JafarSyncStore {
    private var pending: [SyncEnvelope] = []
    private var appliedVersions: [String: Int64] = [:]

    func enqueue(_ envelope: SyncEnvelope) {
        pending.append(envelope)
    }

    func pendingChanges() -> [SyncEnvelope] {
        pending
    }

    func markUploaded(_ envelope: SyncEnvelope) {
        pending.removeAll { $0.entityType == envelope.entityType && $0.entityId == envelope.entityId && $0.version <= envelope.version }
        appliedVersions["\(envelope.entityType):\(envelope.entityId)"] = envelope.version
    }

    func shouldApply(_ envelope: SyncEnvelope) -> Bool {
        let key = "\(envelope.entityType):\(envelope.entityId)"
        let current = appliedVersions[key, default: 0]
        guard envelope.version > current else { return false }
        appliedVersions[key] = envelope.version
        return true
    }
}

actor JafarSyncService {
    private let store: JafarSyncStore

    init(store: JafarSyncStore = JafarSyncStore()) {
        self.store = store
    }

    func recordLocalChange(
        deviceId: String,
        userId: String,
        entityType: String,
        entityId: String,
        version: Int64,
        operation: String,
        payload: Data
    ) async {
        await store.enqueue(SyncEnvelope(
            deviceId: deviceId,
            userId: userId,
            entityType: entityType,
            entityId: entityId,
            version: version,
            operation: operation,
            payload: payload,
            updatedAt: Date()
        ))
    }

    func recoverPendingChanges() async -> [SyncEnvelope] {
        await store.pendingChanges()
    }
}
