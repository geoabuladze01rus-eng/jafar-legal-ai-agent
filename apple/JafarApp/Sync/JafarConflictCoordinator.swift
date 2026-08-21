import Foundation

@MainActor
final class JafarConflictCoordinator: ObservableObject {
    @Published private(set) var conflict: SyncConflict?
    @Published private(set) var localSummary = ""
    @Published private(set) var remoteSummary = ""

    private let resolver: JafarConflictResolver
    private let notificationCenter: JafarNotificationCenter

    init(
        resolver: JafarConflictResolver = JafarConflictResolver(),
        notificationCenter: JafarNotificationCenter
    ) {
        self.resolver = resolver
        self.notificationCenter = notificationCenter
    }

    func handle(local: SyncEnvelope, remote: SyncEnvelope) -> SyncConflictDecision {
        let decision = resolver.decide(local: local, remote: remote)
        guard decision == .requiresUserReview else { return decision }

        conflict = resolver.conflict(local: local, remote: remote)
        localSummary = local.payload
        remoteSummary = remote.payload
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

    func keepLocal() {
        guard let conflict else { return }
        notificationCenter.remove(id: "sync-conflict-\(conflict.entityType)-\(conflict.entityId)")
        self.conflict = nil
    }

    func acceptRemote() {
        guard let conflict else { return }
        notificationCenter.remove(id: "sync-conflict-\(conflict.entityType)-\(conflict.entityId)")
        self.conflict = nil
    }

    func postpone() {
        conflict = nil
    }
}
