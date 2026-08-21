import Foundation

struct JafarPendingVoiceAction: Sendable, Identifiable {
    let id: UUID
    let summary: String
    let action: JafarVoiceAction
    let createdAt: Date
}

@MainActor
final class JafarVoiceConfirmationCoordinator: ObservableObject {
    @Published private(set) var pending: JafarPendingVoiceAction?

    func requestConfirmation(for action: JafarVoiceAction, summary: String) {
        guard action != .unknown else { return }
        pending = JafarPendingVoiceAction(
            id: UUID(),
            summary: summary,
            action: action,
            createdAt: Date()
        )
    }

    func confirm() -> JafarPendingVoiceAction? {
        defer { pending = nil }
        return pending
    }

    func cancel() {
        pending = nil
    }
}
