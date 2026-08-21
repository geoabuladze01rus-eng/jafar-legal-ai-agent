import Foundation

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
        payload: Data,
        requiresLegalReview: Bool = false
    ) async {
        await store.enqueue(SyncEnvelope(
            deviceId: deviceId,
            userId: userId,
            entityType: entityType,
            entityId: entityId,
            version: version,
            operation: operation,
            payload: payload,
            updatedAt: Date(),
            requiresLegalReview: requiresLegalReview
        ))
    }

    func recoverPendingChanges() async -> [SyncEnvelope] {
        await store.pendingChanges()
    }
}
