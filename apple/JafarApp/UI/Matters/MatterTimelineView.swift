import SwiftUI

@MainActor final class JafarMatterTimelineViewModel: ObservableObject {
    enum State { case idle, loading, loaded([MatterEventDTO]), empty, failed(String) }
    @Published private(set) var state: State = .idle
    func load(id: String) { state = .loading; Task { await fetch(id: id) } }
    func retry(id: String) { load(id: id) }
    private func fetch(id: String) async { guard let client = JafarClientConfiguration.configuredRemoteClient() else { state = .failed("Backend недоступен"); return }; do { let events = try await MatterClient(endpoint: client.endpoint, apiKey: client.apiKey).events(id: id); state = events.isEmpty ? .empty : .loaded(events) } catch { state = .failed("Не удалось загрузить хронологию") } }
}

struct MatterTimelineView: View {
    let matterID: String
    @StateObject private var model = JafarMatterTimelineViewModel()
    var body: some View { Group { switch model.state { case .idle, .loading: ProgressView("Загружаю хронологию…"); case .empty: Text("Хронология дела пока пуста").foregroundStyle(JafarPalette.secondary); case let .failed(message): VStack { Text(message).foregroundStyle(.orange); Button("Повторить") { model.retry(id: matterID) } }; case let .loaded(events): VStack(alignment: .leading, spacing: 12) { ForEach(events) { event in JafarCard(title: event.title) { Text(event.eventDate.formatted(date: .abbreviated, time: .shortened)); if let description = event.description { Text(description) }; if let source = event.sourceDocument { Label("Документ · \(source)", systemImage: "doc.text").foregroundStyle(JafarPalette.gold) } } } } } }.task { model.load(id: matterID) } }
}
