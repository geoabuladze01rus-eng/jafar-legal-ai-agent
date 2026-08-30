import Foundation
import SwiftUI

enum CalendarEventTone: Equatable {
    case deadline, hearing, investigation, meeting, task, filed, completed

    var color: Color {
        switch self {
        case .deadline: JafarPalette.warning
        case .hearing, .filed: JafarPalette.accentGold
        case .investigation, .meeting: JafarPalette.accentBlue
        case .task: JafarPalette.textSecondary
        case .completed: JafarPalette.success
        }
    }

    var symbol: String {
        switch self {
        case .deadline: "exclamationmark.triangle.fill"
        case .hearing: "building.columns.fill"
        case .investigation: "magnifyingglass"
        case .meeting: "person.2.fill"
        case .task: "checklist"
        case .filed: "tray.and.arrow.up.fill"
        case .completed: "checkmark.circle.fill"
        }
    }

    var label: String {
        switch self {
        case .deadline: "Процессуальный срок"
        case .hearing: "Судебное заседание"
        case .investigation: "Следственное действие"
        case .meeting: "Встреча"
        case .task: "Задача"
        case .filed: "Подача документа"
        case .completed: "Выполнено"
        }
    }
}

enum CalendarVerification: Equatable {
    case confirmed, candidate, needsReview

    var label: String? {
        switch self {
        case .confirmed: nil
        case .candidate: "Требует проверки"
        case .needsReview: "Требует подтверждения адвокатом"
        }
    }

    var symbol: String? {
        switch self {
        case .confirmed: nil
        case .candidate: "eye.fill"
        case .needsReview: "exclamationmark.shield.fill"
        }
    }
}

struct CalendarPresentationEvent: Identifiable, Equatable {
    let id: String
    let date: Date
    let time: String?
    let title: String
    let matter: String?
    let caseNumber: String?
    let court: String?
    let source: String?
    let tone: CalendarEventTone
    let verification: CalendarVerification

    var day: Int { Calendar.current.component(.day, from: date) }
}

struct CalendarCriticalDeadline: Identifiable, Equatable {
    let event: CalendarPresentationEvent
    let remaining: String
    let urgency: CalendarDeadlineUrgency

    var id: String { event.id }
}

enum CalendarDeadlineUrgency: Equatable {
    case critical, high, attention, normal

    var color: Color {
        switch self {
        case .critical: JafarPalette.danger
        case .high, .attention: JafarPalette.warning
        case .normal: JafarPalette.textSecondary
        }
    }
}

struct CalendarMatterContext: Equatable {
    let title: String
    let subtitle: String
    let type: String?
    let court: String?
    let priority: String?
    let status: String?
    let isGlobal: Bool
}

struct CalendarPresentation: Equatable {
    let context: CalendarMatterContext
    let events: [CalendarPresentationEvent]
    let initialMonth: Date
    let intelligenceItems: [String]

    static let prototype: CalendarPresentation = {
        let calendar = Calendar.current
        func date(_ day: Int, _ hour: Int = 12) -> Date {
            calendar.date(from: DateComponents(year: 2026, month: 5, day: day, hour: hour)) ?? .now
        }
        let matter = "Павлик В.А."
        let number = "A-1234/2026"
        return CalendarPresentation(
            context: CalendarMatterContext(title: "Дело A-1234/2026", subtitle: matter, type: "Арбитраж", court: "АС г. Москвы", priority: "Высокий приоритет", status: "В производстве", isGlobal: false),
            events: [
                CalendarPresentationEvent(id: "hearing-18", date: date(18, 10), time: "10:30", title: "Судебное заседание", matter: matter, caseNumber: number, court: "Арбитражный суд", source: nil, tone: .hearing, verification: .confirmed),
                CalendarPresentationEvent(id: "meeting-19", date: date(19, 15), time: "15:00", title: "Встреча с доверителем", matter: matter, caseNumber: number, court: nil, source: nil, tone: .meeting, verification: .confirmed),
                CalendarPresentationEvent(id: "deadline-20", date: date(20, 18), time: "до 18:00", title: "Подать возражения", matter: matter, caseNumber: number, court: nil, source: nil, tone: .deadline, verification: .confirmed),
                CalendarPresentationEvent(id: "filed-21", date: date(21, 11), time: "11:00", title: "Подача документа", matter: matter, caseNumber: number, court: nil, source: nil, tone: .filed, verification: .confirmed),
                CalendarPresentationEvent(id: "task-22", date: date(22, 16), time: "до 16:00", title: "Подготовить ходатайство", matter: matter, caseNumber: number, court: nil, source: nil, tone: .deadline, verification: .confirmed),
                CalendarPresentationEvent(id: "investigation-25", date: date(25, 9), time: "09:00", title: "Следственное действие", matter: matter, caseNumber: number, court: nil, source: nil, tone: .investigation, verification: .confirmed),
                CalendarPresentationEvent(id: "fee-25", date: date(25, 17), time: "до 17:00", title: "Оплата госпошлины", matter: matter, caseNumber: number, court: nil, source: nil, tone: .deadline, verification: .confirmed),
                CalendarPresentationEvent(id: "task-27", date: date(27, 12), time: "12:00", title: "Проверить приложения", matter: matter, caseNumber: number, court: nil, source: nil, tone: .task, verification: .confirmed),
                CalendarPresentationEvent(id: "court-30", date: date(30, 14), time: "до 14:00", title: "Ответ на запрос суда", matter: matter, caseNumber: number, court: nil, source: nil, tone: .deadline, verification: .confirmed),
                CalendarPresentationEvent(id: "complete-31", date: date(31, 10), time: "10:00", title: "Сверить позицию", matter: matter, caseNumber: number, court: nil, source: nil, tone: .completed, verification: .confirmed)
            ],
            initialMonth: date(18),
            intelligenceItems: ["Критические сроки", "Возможные пересечения", "Процессуальные риски", "Подготовка к заседаниям"]
        )
    }()
}

enum CalendarPresentationAdapter {
    static func make(snapshot: DashboardSnapshot, demoMode: Bool, matter: DashboardMatter? = nil) -> CalendarPresentation {
        if demoMode { return .prototype }

        let visibleMatters = matter.map { [$0] } ?? snapshot.matters
        let matterByID = Dictionary(uniqueKeysWithValues: snapshot.matters.map { ($0.id, $0) })
        let deadlineEvents = visibleMatters.compactMap { presentationDeadline(for: $0) }
        let signalEvents = snapshot.signals.compactMap { signal -> CalendarPresentationEvent? in
            guard matter == nil || signal.matterId == matter?.id,
                  let date = CalendarDateParser.date(from: signal.dueDate) else { return nil }
            let linkedMatter = signal.matterId.flatMap { matterByID[$0] }
            return CalendarPresentationEvent(
                id: "signal-\(signal.id)",
                date: date,
                time: CalendarDateParser.time(from: signal.dueDate),
                title: signal.title,
                matter: linkedMatter?.clientName ?? linkedMatter?.title,
                caseNumber: linkedMatter?.caseNumber,
                court: nil,
                source: signal.body.isEmpty ? nil : signal.body,
                tone: tone(for: signal.kind, title: signal.title),
                verification: signal.requiresApproval ? .candidate : .confirmed
            )
        }
        let events = (deadlineEvents + signalEvents)
            .sorted { $0.date == $1.date ? $0.title < $1.title : $0.date < $1.date }
        let context = makeContext(matter: matter, matters: visibleMatters)
        let initialMonth = events.first.map { Calendar.current.date(from: Calendar.current.dateComponents([.year, .month], from: $0.date)) ?? .now } ?? Calendar.current.date(from: Calendar.current.dateComponents([.year, .month], from: .now)) ?? .now
        let confirmedDeadlines = events.filter { $0.tone == .deadline && $0.verification == .confirmed }.count
        let candidates = events.filter { $0.verification != .confirmed }.count
        let hearings = events.filter { $0.tone == .hearing && $0.verification == .confirmed }.count
        var intelligence: [String] = []
        intelligence.append(confirmedDeadlines > 0 ? "Подтверждённых сроков: \(confirmedDeadlines)" : "Недостаточно данных для анализа сроков")
        intelligence.append(hearings > 0 ? "Ближайшие заседания: \(hearings)" : "Данные о заседаниях отсутствуют")
        intelligence.append(candidates > 0 ? "Требуют проверки: \(candidates)" : "Пересечения не подтверждены")
        intelligence.append("Процессуальные риски: только по подтверждённым данным")
        return CalendarPresentation(context: context, events: events, initialMonth: initialMonth, intelligenceItems: intelligence)
    }

    static func criticalDeadlines(from events: [CalendarPresentationEvent], reference: Date = .now) -> [CalendarCriticalDeadline] {
        events
            .filter { $0.tone == .deadline && $0.verification == .confirmed }
            .sorted { $0.date < $1.date }
            .prefix(4)
            .map { event in
                let days = Calendar.current.dateComponents([.day], from: Calendar.current.startOfDay(for: reference), to: Calendar.current.startOfDay(for: event.date)).day ?? 0
                let urgency: CalendarDeadlineUrgency
                switch days {
                case ...2: urgency = .critical
                case 3...7: urgency = .high
                case 8...14: urgency = .attention
                default: urgency = .normal
                }
                let remaining = days < 0 ? "Просрочено" : days == 0 ? "Сегодня" : "\(days) \(dayWord(days))"
                return CalendarCriticalDeadline(event: event, remaining: remaining, urgency: urgency)
            }
    }

    static func upcomingHearings(from events: [CalendarPresentationEvent], reference: Date = .now) -> [CalendarPresentationEvent] {
        events.filter { $0.tone == .hearing && $0.verification == .confirmed && $0.date >= Calendar.current.startOfDay(for: reference) }
            .sorted { $0.date < $1.date }
            .prefix(3)
            .map { $0 }
    }

    private static func presentationDeadline(for matter: DashboardMatter) -> CalendarPresentationEvent? {
        guard let title = matter.nextDeadlineTitle?.trimmedNonEmpty,
              let date = CalendarDateParser.date(from: matter.nextDeadlineDate) else { return nil }
        return CalendarPresentationEvent(
            id: "matter-deadline-\(matter.id)",
            date: date,
            time: CalendarDateParser.time(from: matter.nextDeadlineDate),
            title: title,
            matter: matter.clientName ?? matter.title,
            caseNumber: matter.caseNumber,
            court: nil,
            source: nil,
            tone: tone(for: matter.matterType, title: title),
            verification: .confirmed
        )
    }

    private static func makeContext(matter: DashboardMatter?, matters: [DashboardMatter]) -> CalendarMatterContext {
        if let matter {
            return CalendarMatterContext(
                title: matter.caseNumber?.trimmedNonEmpty ?? matter.title,
                subtitle: matter.clientName?.trimmedNonEmpty ?? matter.title,
                type: matter.matterType.trimmedNonEmpty,
                court: nil,
                priority: matter.overdueDeadlineCount > 0 ? "Требует внимания" : nil,
                status: matter.status.trimmedNonEmpty,
                isGlobal: false
            )
        }
        return CalendarMatterContext(
            title: "Все дела",
            subtitle: matters.isEmpty ? "Подключённые дела не найдены" : "Календарь по \(matters.count) делам",
            type: nil,
            court: nil,
            priority: nil,
            status: nil,
            isGlobal: true
        )
    }

    private static func tone(for kind: String, title: String) -> CalendarEventTone {
        let value = "\(kind) \(title)".lowercased()
        if value.contains("заседан") || value.contains("слушан") { return .hearing }
        if value.contains("следств") { return .investigation }
        if value.contains("встреч") || value.contains("приём") { return .meeting }
        if value.contains("подач") || value.contains("отправ") { return .filed }
        if value.contains("выполн") || value.contains("заверш") { return .completed }
        if value.contains("задач") || value.contains("провер") { return .task }
        return .deadline
    }

    private static func dayWord(_ days: Int) -> String {
        let value = abs(days) % 100
        if (11...14).contains(value) { return "дней" }
        switch value % 10 {
        case 1: return "день"
        case 2...4: return "дня"
        default: return "дней"
        }
    }
}

private enum CalendarDateParser {
    private static let formats = ["yyyy-MM-dd'T'HH:mm:ssXXXXX", "yyyy-MM-dd'T'HH:mm:ss", "yyyy-MM-dd HH:mm", "dd.MM.yyyy HH:mm", "yyyy-MM-dd", "dd.MM.yyyy"]

    static func date(from value: String?) -> Date? {
        guard let value = value?.trimmedNonEmpty else { return nil }
        if let isoDate = ISO8601DateFormatter().date(from: value) { return isoDate }
        return formats.lazy.compactMap { format in
            let formatter = DateFormatter()
            formatter.locale = Locale(identifier: "ru_RU")
            formatter.dateFormat = format
            return formatter.date(from: value)
        }.first
    }

    static func time(from value: String?) -> String? {
        guard let date = date(from: value), value?.contains(":") == true else { return nil }
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "ru_RU")
        formatter.dateFormat = "HH:mm"
        return formatter.string(from: date)
    }
}

private extension String {
    var trimmedNonEmpty: String? {
        let result = trimmingCharacters(in: .whitespacesAndNewlines)
        return result.isEmpty ? nil : result
    }
}
