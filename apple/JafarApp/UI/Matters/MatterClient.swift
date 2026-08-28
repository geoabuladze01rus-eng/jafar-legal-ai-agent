import Foundation

struct MatterSummary: Codable, Identifiable, Sendable {
    let id: String
    let title: String
    let matterType: String
    let clientName: String?
    let caseNumber: String?
    let status: String
    let updatedAt: Date
    enum CodingKeys: String, CodingKey { case id, title, matterType = "matter_type", clientName = "client_name", caseNumber = "case_number", status, updatedAt = "updated_at" }
}
struct MatterEventDTO: Codable, Identifiable, Sendable { let id: String; let matterID: String; let title: String; let eventDate: Date; let description: String?; let sourceDocument: String?; enum CodingKeys: String, CodingKey { case id, matterID = "matter_id", title, eventDate = "event_date", description, sourceDocument = "source_document" } }

enum MatterClientError: LocalizedError { case unavailable, invalidResponse, notFound, http(Int)
    var errorDescription: String? { switch self { case .unavailable: return "Backend недоступен"; case .invalidResponse: return "API вернул некорректный ответ"; case .notFound: return "Дело не найдено или больше недоступно"; case let .http(code): return "API вернул HTTP \(code)" } }
}

extension MatterClient {
    func events(id: String) async throws -> [MatterEventDTO] { var request = URLRequest(url: endpoint.appendingPathComponent("v1/matters/\(id)/events")); request.httpMethod = "GET"; if let apiKey { request.setValue(apiKey, forHTTPHeaderField: "X-Jafar-API-Key") }; let (data, response) = try await URLSession.shared.data(for: request); guard let http = response as? HTTPURLResponse else { throw MatterClientError.invalidResponse }; if http.statusCode == 404 { throw MatterClientError.notFound }; guard (200...299).contains(http.statusCode) else { throw MatterClientError.http(http.statusCode) }; let decoder = JSONDecoder(); decoder.dateDecodingStrategy = .iso8601; return try decoder.decode([MatterEventDTO].self, from: data).sorted { $0.eventDate < $1.eventDate } }
    func get(id: String) async throws -> MatterSummary {
        var request = URLRequest(url: endpoint.appendingPathComponent("v1/matters/\(id)")); request.httpMethod = "GET"
        if let apiKey { request.setValue(apiKey, forHTTPHeaderField: "X-Jafar-API-Key") }
        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse else { throw MatterClientError.invalidResponse }
        if http.statusCode == 404 { throw MatterClientError.notFound }
        guard (200...299).contains(http.statusCode) else { throw MatterClientError.http(http.statusCode) }
        let decoder = JSONDecoder(); decoder.dateDecodingStrategy = .iso8601
        return try decoder.decode(MatterSummary.self, from: data)
    }
}

@MainActor final class JafarMatterDetailViewModel: ObservableObject {
    enum State { case idle, loading, loaded(MatterSummary), notFound, failed(String) }
    @Published private(set) var state: State = .idle
    func load(id: String) { state = .loading; Task { await fetch(id: id) } }
    func retry(id: String) { load(id: id) }
    private func fetch(id: String) async {
        guard let client = JafarClientConfiguration.configuredRemoteClient() else { state = .failed("Backend недоступен"); return }
        do { state = .loaded(try await MatterClient(endpoint: client.endpoint, apiKey: client.apiKey).get(id: id)) }
        catch MatterClientError.notFound { state = .notFound }
        catch { state = .failed("Не удалось загрузить дело") }
    }
}

struct MatterClient: Sendable {
    let endpoint: URL
    let apiKey: String?
    func list() async throws -> [MatterSummary] {
        var request = URLRequest(url: endpoint.appendingPathComponent("v1/matters")); request.httpMethod = "GET"
        if let apiKey { request.setValue(apiKey, forHTTPHeaderField: "X-Jafar-API-Key") }
        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse else { throw MatterClientError.invalidResponse }
        guard (200...299).contains(http.statusCode) else { throw MatterClientError.http(http.statusCode) }
        let decoder = JSONDecoder(); decoder.dateDecodingStrategy = .iso8601
        return try decoder.decode([MatterSummary].self, from: data)
    }
}

@MainActor final class JafarMattersViewModel: ObservableObject {
    enum State { case idle, loading, loaded([MatterSummary]), empty, failed(String) }
    @Published private(set) var state: State = .idle
    func load() { state = .loading; Task { await fetch() } }
    func retry() { load() }
    private func fetch() async {
        guard let client = JafarClientConfiguration.configuredRemoteClient() else { state = .failed("Backend недоступен"); return }
        do { let matters = try await MatterClient(endpoint: client.endpoint, apiKey: client.apiKey).list(); state = matters.isEmpty ? .empty : .loaded(matters) }
        catch { state = .failed(error.localizedDescription) }
    }
}
