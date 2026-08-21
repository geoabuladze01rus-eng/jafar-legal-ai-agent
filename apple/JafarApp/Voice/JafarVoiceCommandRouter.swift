import Foundation

@MainActor
protocol JafarVoiceCommandHandling: AnyObject {
    func showUrgent() async
    func showDeadlines() async
    func showTasks() async
    func analyzeLatestMail() async
}

@MainActor
final class JafarVoiceCommandRouter {
    weak var handler: JafarVoiceCommandHandling?

    init(handler: JafarVoiceCommandHandling? = nil) {
        self.handler = handler
    }

    func execute(_ action: JafarVoiceAction) async {
        switch action {
        case .showUrgent:
            await handler?.showUrgent()
        case .showDeadlines:
            await handler?.showDeadlines()
        case .showTasks:
            await handler?.showTasks()
        case .analyzeLatestMail:
            await handler?.analyzeLatestMail()
        case .unknown:
            break
        }
    }
}
