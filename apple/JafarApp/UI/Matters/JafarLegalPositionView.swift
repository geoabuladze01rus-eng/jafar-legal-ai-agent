import SwiftUI

@MainActor final class JafarLegalPositionViewModel: ObservableObject {
    enum State { case idle, loading, loaded(MatterLegalPositionDTO), empty, failed(String) }
    @Published private(set) var state: State = .idle
    private var requestID = UUID()
    func load(id: String) { let token = UUID(); requestID = token; state = .loading; Task { guard let c = JafarClientConfiguration.configuredRemoteClient() else { state = .failed("Backend недоступен"); return }; do { let value = try await MatterClient(endpoint: c.endpoint, apiKey: c.apiKey).legalPosition(id: id); guard requestID == token else { return }; state = value.items.isEmpty ? .empty : .loaded(value) } catch { guard requestID == token else { return }; state = .failed("Не удалось загрузить правовую позицию") } } }
}

struct JafarLegalPositionView: View {
    let matterID: String
    @StateObject private var model = JafarLegalPositionViewModel()
    var body: some View { ScrollView { VStack(alignment: .leading, spacing: 14) { Text("Правовая позиция").font(.largeTitle.bold()).foregroundStyle(JafarPalette.text); Text("Контекст дела: \(matterID)").foregroundStyle(JafarPalette.gold); Text("Не проверено адвокатом").font(.caption).foregroundStyle(.orange); content }.padding(28).frame(maxWidth: 1000, alignment: .leading) }.background(JafarPalette.background).task { model.load(id: matterID) } }
    @ViewBuilder private var content: some View { switch model.state { case .idle, .loading: ProgressView("Загружаю правовую позицию…"); case .empty: JafarCard(title: "Правовая позиция") { Text("Правовая позиция пока не сформирована"); Text("Джафар не создаёт юридические выводы без материалов и проверяемых источников.").font(.caption).foregroundStyle(JafarPalette.secondary) }; case let .failed(message): JafarCard(title: "Ошибка") { Text(message).foregroundStyle(.orange); Button("Повторить") { model.load(id: matterID) } }; case let .loaded(position): ForEach(position.items, id: \.text) { item in JafarCard(title: item.kind == "evidence_gap" ? "Пробелы в доказательствах" : item.kind == "risk" ? "Риски" : "Выводы анализа") { Text(item.text); Text("Требует проверки").font(.caption).foregroundStyle(.orange) } } } }
}
