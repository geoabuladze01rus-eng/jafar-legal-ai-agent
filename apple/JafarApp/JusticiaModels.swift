import SwiftUI

enum JusticiaSection: String, CaseIterable, Identifiable {
    case home = "Главная"
    case matters = "Дела"
    case documents = "Документы"
    case analytics = "Аналитика"
    case deadlines = "Сроки"
    case templates = "Шаблоны"
    case publishing = "Автопубликации"
    case transcription = "Транскрибация аудио"
    case settings = "Настройки"

    var id: String { rawValue }

    var icon: String {
        switch self {
        case .home: return "house"
        case .matters: return "briefcase"
        case .documents: return "doc.text"
        case .analytics: return "chart.bar.xaxis"
        case .deadlines: return "calendar"
        case .templates: return "doc.on.doc"
        case .publishing: return "paperplane"
        case .transcription: return "waveform"
        case .settings: return "gearshape"
        }
    }
}

struct JusticiaMatter: Identifiable, Hashable {
    let id = UUID()
    let number: String
    let title: String
    let court: String
    let status: String
    let nextEvent: String
    let risk: String
}

struct JusticiaDocument: Identifiable, Hashable {
    let id = UUID()
    let name: String
    let type: String
    let date: String
    let aiStatus: String
}

struct JusticiaDeadline: Identifiable, Hashable {
    let id = UUID()
    let day: String
    let month: String
    let title: String
    let matter: String
    let urgency: String
}

enum JusticiaDemoData {
    static let matters = [
        JusticiaMatter(number: "А40-123456/2024", title: "Взыскание задолженности по договору поставки", court: "Арбитражный суд г. Москвы", status: "В работе", nextEvent: "Заседание через 5 дней", risk: "Средний"),
        JusticiaMatter(number: "2-1456/2024", title: "Спор по договору подряда", court: "Октябрьский районный суд", status: "Подготовка", nextEvent: "Возражения через 7 дней", risk: "Низкий"),
        JusticiaMatter(number: "А56-98765/2024", title: "Оспаривание решения государственного органа", court: "Арбитражный суд", status: "Апелляция", nextEvent: "Жалоба через 12 дней", risk: "Высокий")
    ]

    static let documents = [
        JusticiaDocument(name: "Исковое заявление.pdf", type: "Исковое заявление", date: "15.10.2024", aiStatus: "Готово"),
        JusticiaDocument(name: "Договор поставки.pdf", type: "Договор", date: "10.10.2024", aiStatus: "Готово"),
        JusticiaDocument(name: "Акт сверки.pdf", type: "Доказательство", date: "08.10.2024", aiStatus: "Готово"),
        JusticiaDocument(name: "Ходатайство.docx", type: "Процессуальный документ", date: "01.11.2024", aiStatus: "Анализ"),
        JusticiaDocument(name: "Апелляционная жалоба.docx", type: "Жалоба", date: "12.12.2024", aiStatus: "Черновик")
    ]

    static let deadlines = [
        JusticiaDeadline(day: "20", month: "окт", title: "Судебное заседание", matter: "А40-123456/2024", urgency: "Через 5 дней"),
        JusticiaDeadline(day: "22", month: "окт", title: "Подать возражения", matter: "2-1456/2024", urgency: "Через 7 дней"),
        JusticiaDeadline(day: "25", month: "окт", title: "Оплата госпошлины", matter: "А56-98765/2024", urgency: "Через 10 дней")
    ]
}
