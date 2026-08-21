import Foundation

@MainActor
protocol JafarConfirmedActionExecuting: AnyObject {
    func createTaskFromVoice(summary: String) async throws
    func createDeadlineFromVoice(summary: String) async throws
    func showDashboardSection(_ section: String) async
}

@MainActor
final class JafarConfirmedActionExecutor {
    private let confirmation: JafarVoiceConfirmationCoordinator
    private weak var executor: JafarConfirmedActionExecuting?

    init(
        confirmation: JafarVoiceConfirmationCoordinator,
        executor: JafarConfirmedActionExecuting
    ) {
        self.confirmation = confirmation
        self.executor = executor
    }

    func confirmPendingAction() async throws {
        guard let action = confirmation.confirm() else { return }
        switch action.action {
        case .showUrgent:
            await executor?.showDashboardSection("urgent")
        case .showDeadlines:
            await executor?.showDashboardSection("deadlines")
        case .showTasks:
            await executor?.showDashboardSection("tasks")
        case .analyzeLatestMail:
            // The actual mail analysis remains delegated to the mail service.
            await executor?.showDashboardSection("latest-mail-analysis")
        case .unknown:
            break
        }
    }
}
