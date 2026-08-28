import Foundation

enum JafarSection: String, CaseIterable, Identifiable {
    case home = "Главная", matters = "Дела", calendar = "Календарь", documents = "Документы", mail = "Почта"
    case radar = "Правовой радар", practice = "Практика", drafts = "Черновики", voice = "Голосовые материалы"
    case analytics = "Аналитика", library = "Библиотека норм", counterparties = "Проверка контрагентов", settings = "Настройки"
    var id: String { rawValue }
    var title: String { rawValue }
    var icon: String { ["Главная":"house", "Дела":"folder", "Календарь":"calendar", "Документы":"doc.text", "Почта":"envelope", "Правовой радар":"scope", "Практика":"briefcase", "Черновики":"square.and.pencil", "Голосовые материалы":"waveform", "Аналитика":"chart.bar", "Библиотека норм":"books.vertical", "Проверка контрагентов":"person.text.rectangle", "Настройки":"gearshape"][rawValue] ?? "circle" }
}
