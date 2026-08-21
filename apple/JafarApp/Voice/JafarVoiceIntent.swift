import AppIntents
import Foundation

enum JafarVoiceAction: String, Sendable {
    case showUrgent = "show_urgent"
    case showDeadlines = "show_deadlines"
    case showTasks = "show_tasks"
    case analyzeLatestMail = "analyze_latest_mail"
    case unknown
}

struct JafarVoiceIntent: AppIntent {
    static var title: LocalizedStringResource = "Джафар"
    static var description = IntentDescription("Голосовая команда для юридического ассистента Джафар.")
    static var openAppWhenRun = false

    @Parameter(title: "Команда")
    var command: String

    func perform() async throws -> some IntentResult & ReturnsValue<String> {
        let action = classify(command)
        switch action {
        case .showUrgent:
            return .result(value: "Показываю срочные риски и ближайшие сроки.")
        case .showDeadlines:
            return .result(value: "Показываю контроль сроков.")
        case .showTasks:
            return .result(value: "Показываю задачи по делам.")
        case .analyzeLatestMail:
            return .result(value: "Запускаю анализ последнего юридически значимого письма.")
        case .unknown:
            return .result(value: "Не удалось однозначно распознать команду. Повторите её.")
        }
    }

    private func classify(_ value: String) -> JafarVoiceAction {
        let text = value.lowercased()
        if text.contains("сроч") || text.contains("горит") { return .showUrgent }
        if text.contains("срок") || text.contains("дедлайн") { return .showDeadlines }
        if text.contains("задач") || text.contains("дела") { return .showTasks }
        if text.contains("почт") || text.contains("письм") || text.contains("mail") { return .analyzeLatestMail }
        return .unknown
    }
}
