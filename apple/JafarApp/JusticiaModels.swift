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
