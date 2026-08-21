import Foundation

@MainActor
protocol JafarDeadlineStore: AnyObject {
    func createDeadline(matterID: UUID, title: String, dueAt: Date, sourceDocumentID: UUID?, basis: String, confidence: Double) async throws
}

@MainActor
final class JafarDeadlineExecutor {
    private let store: JafarDeadlineStore
    private let audit: JafarAuditLogging
    private let deviceID: String

    init(store: JafarDeadlineStore, audit: JafarAuditLogging, deviceID: String) {
        self.store = store
        self.audit = audit
        self.deviceID = deviceID
    }

    func createConfirmedDeadline(
        matterID: UUID,
        title: String,
        dueAt: Date,
        sourceDocumentID: UUID? = nil,
        basis: String,
        confidence: Double
    ) async throws {
        try await store.createDeadline(
            matterID: matterID,
            title: title,
            dueAt: dueAt,
            sourceDocumentID: sourceDocumentID,
            basis: basis,
            confidence: confidence
        )

        try await audit.record(JafarAuditEvent(
            id: UUID(),
            action: "create_deadline",
            entityType: "deadline",
            entityID: nil,
            oldPayload: nil,
            newPayload: [
                "matter_id": matterID.uuidString,
                "title": title,
                "due_at": ISO8601DateFormatter().string(from: dueAt),
                "basis": basis,
                "confidence": String(confidence)
            ],
            deviceID: deviceID,
            source: "voice",
            confirmed: true,
            occurredAt: Date()
        ))
    }
}
