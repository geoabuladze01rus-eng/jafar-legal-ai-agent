import Foundation

@MainActor
final class DeadlineConfirmationCoordinator {
    private let scheduler: DeadlineNotificationScheduler

    init(scheduler: DeadlineNotificationScheduler = DeadlineNotificationScheduler()) {
        self.scheduler = scheduler
    }

    func confirm(
        proposal: DeadlineProposalViewModel,
        dueDate: Date,
        matterId: String,
        taskTitle: String,
        createTask: @escaping (String, String, Date, String) async throws -> Void
    ) async throws {
        try await createTask(
            matterId,
            taskTitle,
            dueDate,
            proposal.sourceId
        )

        let granted = await scheduler.requestPermission()
        guard granted else { return }

        try await scheduler.schedule(
            id: "\(matterId)-\(proposal.sourceId)-\(dueDate.timeIntervalSince1970)",
            title: taskTitle,
            body: "Подтверждённый срок по делу. Источник: \(proposal.basis)",
            dueAt: dueDate
        )
    }
}
