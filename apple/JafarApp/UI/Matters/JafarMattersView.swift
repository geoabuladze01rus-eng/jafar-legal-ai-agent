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
    @ViewBuilder private var content: some View { switch model.state { case .idle, .loading: ProgressView("Загружаю дела…"); case .empty: JafarCard(title: "Список дел") { Text("Дела пока не добавлены").foregroundStyle(JafarPalette.secondary) }; case let .failed(message): JafarCard(title: "Ошибка") { Text(message).foregroundStyle(.orange); Button("Повторить") { model.retry() } }; case let .loaded(matters): ForEach(matters) { matter in NavigationLink { JafarMatterWorkspaceView(identifier: matter.id) } label: { JafarCard(title: matter.title) { if let number = matter.caseNumber { Text(number) }; if let client = matter.clientName { Text(client) }; Text(matter.matterType); Text(matter.status) } }.buttonStyle(.plain) } } }
}

struct JafarMatterWorkspaceView: View {
    let identifier: String
    @StateObject private var model = JafarMatterDetailViewModel()
    @State private var tab = "Обзор"
    private let tabs = ["Обзор", "Хронология", "Документы", "Правовая позиция", "Доказательства", "Риски", "Сроки", "Черновики"]
    var body: some View {
        ScrollView { VStack(alignment: .leading, spacing: 20) {
            workspaceContent
            Picker("Раздел дела", selection: $tab) { ForEach(tabs, id: \.self) { Text($0).tag($0) } }.pickerStyle(.segmented)
            if tab == "Хронология" { MatterTimelineView(matterID: identifier) } else if tab == "Документы" { MatterDocumentsView(matterID: identifier) } else { JafarCard(title: tab) { Text("Раздел будет заполнен после подключения источника данных.").foregroundStyle(JafarPalette.secondary) } }
        }.padding(28).frame(maxWidth: 1100, alignment: .leading) }.background(JafarPalette.background).task { model.load(id: identifier) }
    }
    @ViewBuilder private var workspaceContent: some View { switch model.state { case .idle, .loading: ProgressView("Загружаю дело…"); case .notFound: VStack(alignment: .leading) { Text("Дело не найдено или больше недоступно").foregroundStyle(.orange); Button("Вернуться к списку дел") {} }; case let .failed(message): VStack(alignment: .leading) { Text(message).foregroundStyle(.orange); Button("Повторить") { model.retry(id: identifier) } }; case let .loaded(matter): VStack(alignment: .leading, spacing: 8) { Text(matter.title).font(.largeTitle.bold()).foregroundStyle(JafarPalette.text); if let number = matter.caseNumber { Text("Номер дела: \(number)") }; if let client = matter.clientName { Text("Доверитель: \(client)") }; Text("Тип: \(matter.matterType)"); Text("Статус: \(matter.status)"); Text("Контекст дела: \(matter.title)").foregroundStyle(JafarPalette.gold); Text("ID: \(matter.id)").font(.caption).foregroundStyle(JafarPalette.secondary); Picker("Раздел дела", selection: $tab) { ForEach(tabs, id: \.self) { Text($0).tag($0) } }.pickerStyle(.segmented); JafarCard(title: tab) { Text("Раздел будет заполнен после подключения источника данных.").foregroundStyle(JafarPalette.secondary) } } } }
}
