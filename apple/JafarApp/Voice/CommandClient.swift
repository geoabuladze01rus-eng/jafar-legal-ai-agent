import Foundation

struct CommandRequest: Codable, Sendable {
    let text: String
    let userId: String
    let sourceDevice: String
}

struct CommandResponse: Codable, Sendable {
    let message: String
}

protocol CommandClient: Sendable {
    func send(request: CommandRequest) async throws -> CommandResponse
}

struct LocalCommandClient: CommandClient {
    func send(request: CommandRequest) async throws -> CommandResponse {
        CommandResponse(message: "Команда получена локально: \(request.text)")
    }
}

struct RemoteCommandClient: CommandClient {
    let endpoint: URL
    let session: URLSession
    let apiKey: String?

    init(endpoint: URL, session: URLSession = .shared, apiKey: String? = nil) {
        self.endpoint = endpoint
        self.session = session
        self.apiKey = apiKey
    }

    func send(request: CommandRequest) async throws -> CommandResponse {
        var urlRequest = URLRequest(url: endpoint)
        urlRequest.httpMethod = "POST"
        urlRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")
        if let apiKey {
            urlRequest.setValue(apiKey, forHTTPHeaderField: "X-Jafar-API-Key")
        }
        urlRequest.httpBody = try JSONEncoder().encode(request)

        let (data, response) = try await session.data(for: urlRequest)
        guard let httpResponse = response as? HTTPURLResponse else {
            throw CommandClientError.invalidResponse
        }
        guard (200...299).contains(httpResponse.statusCode) else {
            throw CommandClientError.httpStatus(httpResponse.statusCode)
        }
        return try JSONDecoder().decode(CommandResponse.self, from: data)
    }
}

enum CommandClientError: Error, Sendable {
    case invalidResponse
    case httpStatus(Int)
}
