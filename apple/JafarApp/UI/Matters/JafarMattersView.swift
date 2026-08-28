import SwiftUI

struct JafarMattersView: View {
    @State private var selectedMatter: String?
    var body: some View {
        NavigationStack {
            VStack(alignment: .leading, spacing: 20) {
                Text("Дела").font(.largeTitle.bold()).foregroundStyle(JafarPalette.text)
                Text("Уголовные, гражданские и арбитражные производства").foregroundStyle(JafarPalette.secondary)
                Text("Поиск и фильтры появятся после подключения live-агрегации дел.").font(.caption).foregroundStyle(JafarPalette.secondary)
                JafarCard(title: "Список дел") {
                    Label("Дела пока не загружены", systemImage: "folder").foregroundStyle(JafarPalette.secondary)
                    Text("Экран готов к реальным данным MatterRepository; частные данные не подставляются автоматически.").font(.caption).foregroundStyle(JafarPalette.secondary)
                    Button("Открыть дело по ID") {}.disabled(true).accessibilityHint("Будет доступно после подключения API дел")
                }
                Spacer()
            }.padding(28).frame(maxWidth: 1000, alignment: .leading).background(JafarPalette.background)
        }
    }
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
