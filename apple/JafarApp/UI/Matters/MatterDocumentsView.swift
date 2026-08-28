import SwiftUI

struct MatterDocumentDTO: Codable, Identifiable, Sendable { let id: String; let matterID: String; let filename: String; let contentType: String?; let source: String?; let createdAt: Date; let processingStatus: String; enum CodingKeys: String, CodingKey { case id, matterID = "matter_id", filename, contentType = "content_type", source, createdAt = "created_at", processingStatus = "processing_status" } }

@MainActor final class JafarMatterDocumentsViewModel: ObservableObject { enum State { case idle, loading, loaded([MatterDocumentDTO]), empty, failed(String) }; @Published var state: State = .idle; func load(id: String) { state = .loading; Task { guard let c = JafarClientConfiguration.configuredRemoteClient() else { state = .failed("Backend недоступен"); return }; do { let d = try await MatterClient(endpoint: c.endpoint, apiKey: c.apiKey).documents(id: id); state = d.isEmpty ? .empty : .loaded(d) } catch { state = .failed("Не удалось загрузить документы") } } } }

struct MatterDocumentsView: View {
    let matterID: String
    @StateObject private var model = JafarMatterDocumentsViewModel()
    var body: some View { Group { switch model.state { case .idle, .loading: ProgressView("Загружаю документы…"); case .empty: Text("Документы по делу пока не загружены"); case let .failed(m): VStack { Text(m).foregroundStyle(.orange); Button("Повторить") { model.load(id: matterID) } }; case let .loaded(ds): ForEach(ds) { d in JafarCard(title: d.filename) { if let s = d.source { Text(s) }; if let t = d.contentType { Text(t).font(.caption) }; Text("Добавлен: \(d.createdAt.formatted(date: .abbreviated, time: .shortened))"); Text(d.processingStatus) } } } }.task { model.load(id: matterID) } }
}
