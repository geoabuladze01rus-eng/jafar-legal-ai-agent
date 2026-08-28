import SwiftUI

struct JafarMattersView: View {
    @StateObject private var model = JafarMattersViewModel()
    var body: some View {
        NavigationStack {
            VStack(alignment: .leading, spacing: 20) {
                Text("Дела").font(.largeTitle.bold()).foregroundStyle(JafarPalette.text)
                Text("Уголовные, гражданские и арбитражные производства").foregroundStyle(JafarPalette.secondary)
                Text("Поиск и фильтры появятся после подключения live-агрегации дел.").font(.caption).foregroundStyle(JafarPalette.secondary)
                content
                Spacer()
            }.padding(28).frame(maxWidth: 1000, alignment: .leading).background(JafarPalette.background)
        }.task { model.load() }
    }
    @ViewBuilder private var content: some View { switch model.state { case .idle, .loading: ProgressView("Загружаю дела…"); case .empty: JafarCard(title: "Список дел") { Text("Дела пока не добавлены").foregroundStyle(JafarPalette.secondary) }; case let .failed(message): JafarCard(title: "Ошибка") { Text(message).foregroundStyle(.orange); Button("Повторить") { model.retry() } }; case let .loaded(matters): ForEach(matters) { matter in JafarCard(title: matter.title) { if let number = matter.caseNumber { Text(number) }; if let client = matter.clientName { Text(client) }; Text(matter.matterType); Text(matter.status) } } } }
}

struct JafarMatterWorkspaceView: View {
    let identifier: String
    @State private var tab = "Обзор"
    private let tabs = ["Обзор", "Хронология", "Документы", "Правовая позиция", "Доказательства", "Риски", "Сроки", "Черновики"]
    var body: some View {
        ScrollView { VStack(alignment: .leading, spacing: 20) {
            Text("Дело").font(.largeTitle.bold()).foregroundStyle(JafarPalette.text)
            Text("Контекст: \(identifier)").font(.headline).foregroundStyle(JafarPalette.gold)
            Text("Данные дела пока недоступны").foregroundStyle(JafarPalette.secondary)
            Picker("Раздел дела", selection: $tab) { ForEach(tabs, id: \.self) { Text($0).tag($0) } }.pickerStyle(.segmented)
            JafarCard(title: tab) { Text("Раздел будет заполнен после подключения источника данных.").foregroundStyle(JafarPalette.secondary) }
        }.padding(28).frame(maxWidth: 1100, alignment: .leading) }.background(JafarPalette.background)
    }
}
