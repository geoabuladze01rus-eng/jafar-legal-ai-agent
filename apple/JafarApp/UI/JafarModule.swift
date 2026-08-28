import SwiftUI

enum JafarModule: String, CaseIterable, Identifiable, Hashable {
    case cases
    case documents
    case practice
    case mail
    case council
    case approvals

    var id: String { rawValue }

    var title: String {
        switch self {
        case .cases: "Дела"
        case .documents: "Документы"
        case .practice: "Судебная практика"
        case .mail: "Почта"
        case .council: "ИИ-консилиум"
        case .approvals: "На одобрение"
        }
    }

    var subtitle: String {
        switch self {
        case .cases: "Позиция, риски и сроки"
        case .documents: "Анализ и подготовка"
        case .practice: "ВС РФ и применимость"
        case .mail: "Важные письма и действия"
        case .council: "Мнения моделей и разногласия"
        case .approvals: "Правки только после проверки"
        }
    }

    var icon: String {
        switch self {
        case .cases: "briefcase.fill"
        case .documents: "doc.text.magnifyingglass"
        case .practice: "building.columns.fill"
        case .mail: "envelope.fill"
        case .council: "person.3.fill"
        case .approvals: "checkmark.seal.fill"
        }
    }

    var detailPoints: [String] {
        switch self {
        case .cases:
            ["Карта позиции обвинения и защиты", "Процессуальные сроки и риски", "Изменения практики по активному делу"]
        case .documents:
            ["Source-traceable анализ", "Проверка ссылок и authorities", "Точечные правки с lawyer approval"]
        case .practice:
            ["Официальные позиции Верховного Суда РФ", "Applicability и precedent freshness", "История развития правовой позиции"]
        case .mail:
            ["Приоритетные письма", "Юридические документы и вложения", "Сроки, ответы и обязательства"]
        case .council:
            ["Независимые ответы моделей", "Разногласия показываются явно", "Конфиденциальные материалы — fail closed"]
        case .approvals:
            ["Stale-фрагменты документов", "Сравнение старой и новой редакции", "Immutable approval и audit trail"]
        }
    }
}
