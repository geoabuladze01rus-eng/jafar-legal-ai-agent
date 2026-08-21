import Foundation
import Combine

@MainActor
final class JafarConflictCoordinator: ObservableObject {
    @Published private(set) var conflict: SyncConflict?
    @Published private(set) var localSummary = ""
    @Published private(set) var remoteSummary = ""

    private let resolver: JafarConflictResolver
    private let notificationCenter: JafarNotificationCenter
    private let audit: JafarAuditLogging
    private let deviceID: String

    init(
        resolver: JafarConflictResolver = JafarConflictResolver(),
        notificationCenter: JafarNotificationCenter,
        audit: JafarAuditLogging,
        deviceID: String
    ) {
        self.resolver = resolver
        self.notificationCenter = notificationCenter
        self.audit = audit
        self.deviceID = deviceID
    }

    func handle(local: SyncEnvelope, remote: SyncEnvelope) -> SyncConflictDecision {
        let decision = resolver.decide(local: local, remote: remote)
        guard decision == .requiresUserReview else { return decision }

        conflict = resolver.conflict(local: local, remote: remote)
        localSummary = summary(for: local.payload)
        remoteSummary = summary(for: remote.payload)
        notificationCenter.add(JafarNotificationItem(
            id: "sync-conflict-\(local.entityType)-\(local.entityId)",
            kind: .approvalRequired,
            title: "Требуется разрешить конфликт",
            body: "Изменения по юридически значимым данным отличаются на устройствах.",
            createdAt: Date(),
            priority: 100,
            requiresApproval: true
        ))
        return decision
    }

    func keepLocal() async throws {
        guard let conflict else { return }
        try await recordResolution(conflict: conflict, resolution: "keep_local")
        notificationCenter.remove(id: "sync-conflict-\(conflict.entityType)-\(conflict.entityId)")
        self.conflict = nil
    }

    func acceptRemote() async throws {
        guard let conflict else { return }
        try await recordResolution(conflict: conflict, resolution: "accept_remote")
        notificationCenter.remove(id: "sync-conflict-\(conflict.entityType)-\(conflict.entityId)")
        self.conflict = nil
    }

    func postpone() {
        conflict = nil
    }

    private func summary(for payload: Data) -> String {
        if let string = String(data: payload, encoding: .utf8) { return string }
        return "Бинарные данные (\(payload.count) байт)"
    }

    private func recordResolution(conflict: SyncConflict, resolution: String) async throws {
        try await audit.record(JafarAuditEvent(
            id: UUID(),
            action: "resolve_sync_conflict",
            entityType: conflict.entityType,
            entityID: UUID(uuidString: conflict.entityId),
            oldPayload: [
                "local_version": String(conflict.localVersion),
                "remote_version": String(conflict.remoteVersion)
            ],
            newPayload: ["resolution": resolution],
            deviceID: deviceID,
            source: "sync_conflict",
            confirmed: true,
            occurredAt: Date()
        ))
    }
}
