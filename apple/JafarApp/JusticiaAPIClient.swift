import Foundation

struct JusticiaDeadlineDTO: Codable, Hashable {
    let title: String
    let dueDate: String?
    let sourceText: String?
    let confidence: Double

    enum CodingKeys: String, CodingKey {
        case title
        case dueDate = "due_date"
        case sourceText = "source_text"
        case confidence
    }
}

struct JusticiaMatterDTO: Codable, Identifiable, Hashable {
    let id: String
    let title: String
    let matterType: String
    let clientName: String?
    let opposingParty: String?
    let courtOrAuthority: String?
    let caseNumber: String?
    let status: String
    let deadlines: [JusticiaDeadlineDTO]
    let createdAt: String
    let updatedAt: String

    enum CodingKeys: String, CodingKey {
        case id
        case title
        case matterType = "matter_type"
        case clientName = "client_name"
        case opposingParty = "opposing_party"
        case courtOrAuthority = "court_or_authority"
        case caseNumber = "case_number"
        case status
        case deadlines
        case createdAt = "created_at"
        case updatedAt = "updated_at"
    }

    var displayNumber: String {
        if let caseNumber, !caseNumber.isEmpty { return caseNumber }
        return "Без номера"
    }

    var displayCourt: String {
        courtOrAuthority?.isEmpty == false ? courtOrAuthority! : "Не указан"
    }

    var displayStatus: String {
        switch status.lowercased() {
        case "active": "В работе"
        case "closed": "Завершено"
        case "paused": "Приостановлено"
        default: status
        }
    }

    var nextDeadlineText: String {
        guard let deadline = deadlines.first else { return "Сроки не добавлены" }
        if let dueDate = deadline.dueDate, !dueDate.isEmpty { return "\(deadline.title) · \(dueDate)" }
        return deadline.title
    }
}

struct JusticiaDocumentDTO: Codable, Identifiable, Hashable {
    let documentId: String
    let matterId: String
    let filename: String
    let mediaType: String
    let fingerprint: String
    let byteCount: Int
    let state: String
    let citations: [String]

    var id: String { documentId }

    enum CodingKeys: String, CodingKey {
        case documentId = "document_id"
        case matterId = "matter_id"
        case filename
        case mediaType = "media_type"
        case fingerprint
        case byteCount = "byte_count"
        case state
        case citations
    }

    var displayState: String {
        switch state.lowercased() {
        case "ready": "Готово"
        case "processing": "Обработка"
        case "failed": "Ошибка"
        default: state
        }
    }
}

struct JusticiaCreateMatterRequest: Codable {
    let title: String
    let matterType: String
    let clientName: String?
    let opposingParty: String?
    let courtOrAuthority: String?
    let caseNumber: String?

    enum CodingKeys: String, CodingKey {
        case title
        case matterType = "matter_type"
        case clientName = "client_name"
        case opposingParty = "opposing_party"
        case courtOrAuthority = "court_or_authority"
        case caseNumber = "case_number"
    }
}

enum JusticiaAPIError: LocalizedError {
    case unavailable
    case unauthorized
    case invalidResponse
    case httpStatus(Int, String)
    case invalidPayload

    var errorDescription: String? {
        switch self {
        case .unavailable: "Локальный сервис «Юстиции» недоступен."
        case .unauthorized: "Локальная сессия «Юстиции» требует повторной авторизации."
        case .invalidResponse: "Получен некорректный ответ локального сервиса."
        case .httpStatus(let status, let detail):
            detail.isEmpty ? "Локальный сервис вернул ошибку \(status)." : detail
        case .invalidPayload: "Не удалось прочитать данные локального сервиса."
        }
    }
}

struct JusticiaAPIClient {
    let baseURL: URL
    let token: String
    let session: URLSession

    init(baseURL: URL, token: String, session: URLSession = .shared) {
        self.baseURL = baseURL
        self.token = token
        self.session = session
    }

    func listMatters() async throws -> [JusticiaMatterDTO] {
        try await request(path: "/v1/matters", method: "GET", body: Optional<Data>.none)
    }

    func createMatter(
        title: String,
        matterType: String = "general",
        clientName: String? = nil,
        opposingParty: String? = nil,
        courtOrAuthority: String? = nil,
        caseNumber: String? = nil
    ) async throws -> JusticiaMatterDTO {
        let payload = JusticiaCreateMatterRequest(
            title: title,
            matterType: matterType,
            clientName: clientName,
            opposingParty: opposingParty,
            courtOrAuthority: courtOrAuthority,
            caseNumber: caseNumber
        )
        return try await request(path: "/v1/matters", method: "POST", body: JSONEncoder().encode(payload))
    }

    func listDocuments(matterID: String) async throws -> [JusticiaDocumentDTO] {
        try await request(path: "/v1/matters/\(matterID)/documents", method: "GET", body: Optional<Data>.none)
    }

    func importDocument(matterID: String, fileURL: URL) async throws -> JusticiaDocumentDTO {
        let didAccess = fileURL.startAccessingSecurityScopedResource()
        defer {
            if didAccess { fileURL.stopAccessingSecurityScopedResource() }
        }

        let data = try Data(contentsOf: fileURL)
        let boundary = "JusticiaBoundary\(UUID().uuidString)"
        var body = Data()
        body.append("--\(boundary)\r\n".data(using: .utf8)!)
        body.append("Content-Disposition: form-data; name=\"file\"; filename=\"\(fileURL.lastPathComponent)\"\r\n".data(using: .utf8)!)
        body.append("Content-Type: application/octet-stream\r\n\r\n".data(using: .utf8)!)
        body.append(data)
        body.append("\r\n--\(boundary)--\r\n".data(using: .utf8)!)

        var urlRequest = URLRequest(url: baseURL.appending(path: "/v1/matters/\(matterID)/documents/import"))
        urlRequest.httpMethod = "POST"
        urlRequest.timeoutInterval = 120
        urlRequest.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        urlRequest.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        urlRequest.httpBody = body

        let (responseData, response) = try await session.data(for: urlRequest)
        try validate(response: response, data: responseData)
        guard let decoded = try? JSONDecoder().decode(JusticiaDocumentDTO.self, from: responseData) else {
            throw JusticiaAPIError.invalidPayload
        }
        return decoded
    }

    private func request<Response: Decodable>(
        path: String,
        method: String,
        body: Data?
    ) async throws -> Response {
        var urlRequest = URLRequest(url: baseURL.appending(path: path))
        urlRequest.httpMethod = method
        urlRequest.timeoutInterval = 60
        urlRequest.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        urlRequest.setValue("application/json", forHTTPHeaderField: "Accept")
        if let body {
            urlRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")
            urlRequest.httpBody = body
        }

        let (data, response) = try await session.data(for: urlRequest)
        try validate(response: response, data: data)
        do {
            return try JSONDecoder().decode(Response.self, from: data)
        } catch {
            throw JusticiaAPIError.invalidPayload
        }
    }

    private func validate(response: URLResponse, data: Data) throws {
        guard let http = response as? HTTPURLResponse else {
            throw JusticiaAPIError.invalidResponse
        }
        if http.statusCode == 401 {
            throw JusticiaAPIError.unauthorized
        }
        guard (200...299).contains(http.statusCode) else {
            let detail = (try? JSONSerialization.jsonObject(with: data))
                .flatMap { $0 as? [String: Any] }?["detail"] as? String ?? ""
            throw JusticiaAPIError.httpStatus(http.statusCode, detail)
        }
    }
}

@MainActor
final class JusticiaWorkspaceStore: ObservableObject {
    @Published private(set) var matters: [JusticiaMatterDTO] = []
    @Published private(set) var documents: [JusticiaDocumentDTO] = []
    @Published var selectedMatterID: String?
    @Published private(set) var isLoading = false
    @Published private(set) var isImporting = false
    @Published var errorMessage: String?

    private var client: JusticiaAPIClient?

    init(client: JusticiaAPIClient? = nil) {
        self.client = client
    }

    var selectedMatter: JusticiaMatterDTO? {
        guard let selectedMatterID else { return nil }
        return matters.first { $0.id == selectedMatterID }
    }

    func configure(client: JusticiaAPIClient?) {
        self.client = client
    }

    func refresh() async {
        guard let client else {
            matters = []
            documents = []
            selectedMatterID = nil
            return
        }
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }
        do {
            matters = try await client.listMatters()
            if selectedMatterID == nil || !matters.contains(where: { $0.id == selectedMatterID }) {
                selectedMatterID = matters.first?.id
            }
            await refreshDocuments()
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func selectMatter(_ matter: JusticiaMatterDTO) async {
        selectedMatterID = matter.id
        await refreshDocuments()
    }

    func createMatter(
        title: String,
        matterType: String,
        clientName: String?,
        opposingParty: String?,
        courtOrAuthority: String?,
        caseNumber: String?
    ) async -> Bool {
        guard let client else { return false }
        errorMessage = nil
        do {
            let created = try await client.createMatter(
                title: title,
                matterType: matterType,
                clientName: normalized(clientName),
                opposingParty: normalized(opposingParty),
                courtOrAuthority: normalized(courtOrAuthority),
                caseNumber: normalized(caseNumber)
            )
            matters.insert(created, at: 0)
            selectedMatterID = created.id
            documents = []
            return true
        } catch {
            errorMessage = error.localizedDescription
            return false
        }
    }

    func refreshDocuments() async {
        guard let client, let matterID = selectedMatterID else {
            documents = []
            return
        }
        do {
            documents = try await client.listDocuments(matterID: matterID)
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func importDocument(from url: URL) async -> Bool {
        guard let client, let matterID = selectedMatterID else { return false }
        isImporting = true
        errorMessage = nil
        defer { isImporting = false }
        do {
            _ = try await client.importDocument(matterID: matterID, fileURL: url)
            await refreshDocuments()
            return true
        } catch {
            errorMessage = error.localizedDescription
            return false
        }
    }

    private func normalized(_ value: String?) -> String? {
        guard let value else { return nil }
        let trimmed = value.trimmingCharacters(in: .whitespacesAndNewlines)
        return trimmed.isEmpty ? nil : trimmed
    }
}
