import Foundation

struct CommandRequest: Codable, Sendable {
    let text: String
    let userId: String
    let sourceDevice: String
    let approved: Bool

    init(text: String, userId: String, sourceDevice: String, approved: Bool = false) {
        self.text = text
        self.userId = userId
        self.sourceDevice = sourceDevice
        self.approved = approved
    }

    enum CodingKeys: String, CodingKey {
        case text
        case userId = "user_id"
        case sourceDevice = "source_device"
        case approved
    }
}

struct CommandResponse: Codable, Sendable {
    let message: String
    let intent: String
    let approvalRequired: Bool
    let requestId: String
    let data: [String: JSONValue]?

    enum CodingKeys: String, CodingKey {
        case message
        case intent
        case approvalRequired = "approval_required"
        case requestId = "request_id"
        case data
    }
}

enum JSONValue: Codable, Sendable, Equatable {
    case string(String)
    case number(Double)
    case bool(Bool)
    case object([String: JSONValue])
    case array([JSONValue])
    case null

    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if container.decodeNil() { self = .null }
        else if let value = try? container.decode(Bool.self) { self = .bool(value) }
        else if let value = try? container.decode(Double.self) { self = .number(value) }
        else if let value = try? container.decode(String.self) { self = .string(value) }
        else if let value = try? container.decode([String: JSONValue].self) { self = .object(value) }
        else if let value = try? container.decode([JSONValue].self) { self = .array(value) }
        else { throw DecodingError.dataCorruptedError(in: container, debugDescription: "Unsupported JSON value") }
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch self {
        case .string(let value): try container.encode(value)
        case .number(let value): try container.encode(value)
        case .bool(let value): try container.encode(value)
        case .object(let value): try container.encode(value)
        case .array(let value): try container.encode(value)
        case .null: try container.encodeNil()
        }
    }
}

protocol CommandClient: Sendable {
    func send(request: CommandRequest) async throws -> CommandResponse
}

struct LocalCommandClient: CommandClient {
    func send(request: CommandRequest) async throws -> CommandResponse {
        CommandResponse(
            message: "Команда получена локально: \(request.text)",
            intent: "local_command",
            approvalRequired: false,
            requestId: UUID().uuidString,
            data: nil
        )
    }
}

struct RemoteCommandClient: CommandClient {
    let endpoint: URL
    let session: URLSession
    let authorizationToken: String?

    init(endpoint: URL, session: URLSession = .shared, authorizationToken: String? = nil) {
        self.endpoint = endpoint
        self.session = session
        self.authorizationToken = authorizationToken
    }

    func send(request: CommandRequest) async throws -> CommandResponse {
        var urlRequest = URLRequest(url: endpoint)
        urlRequest.httpMethod = "POST"
        urlRequest.timeoutInterval = 60
        urlRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")
        urlRequest.setValue("application/json", forHTTPHeaderField: "Accept")
        if let authorizationToken, !authorizationToken.isEmpty {
            urlRequest.setValue("Bearer \(authorizationToken)", forHTTPHeaderField: "Authorization")
        }
        urlRequest.httpBody = try JSONEncoder().encode(request)

        let (data, response) = try await session.data(for: urlRequest)
        guard let httpResponse = response as? HTTPURLResponse else {
            throw CommandClientError.invalidResponse
        }
        guard (200...299).contains(httpResponse.statusCode) else {
            throw CommandClientError.httpStatus(httpResponse.statusCode)
        }
        do {
            return try JSONDecoder().decode(CommandResponse.self, from: data)
        } catch {
            throw CommandClientError.invalidPayload
        }
    }
}

enum CommandClientError: LocalizedError, Sendable {
    case invalidResponse
    case invalidPayload
    case httpStatus(Int)

    var errorDescription: String? {
        switch self {
        case .invalidResponse: "Сервер Джафара вернул некорректный ответ."
        case .invalidPayload: "Не удалось прочитать ответ Джафара."
        case .httpStatus(let status): "Сервер Джафара ответил с ошибкой \(status)."
        }
    }
}
