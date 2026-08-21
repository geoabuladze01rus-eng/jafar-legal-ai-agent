import Foundation

@MainActor
protocol JafarDeadlineStore: AnyObject {
    func createDeadline(matterID: UUID, title: String, dueAt: Date, sourceDocumentID: UUID?, basis: String, confidence: Double) async throws
}

@MainActor
final class JafarDeadlineExecutor {
    private let store: JafarDeadlineStore

    init(store: JafarDeadlineStore) {
        self.store = store
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
    }
}
