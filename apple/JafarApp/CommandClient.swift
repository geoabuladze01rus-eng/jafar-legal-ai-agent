import Foundation

struct CommandRequest: Codable {
    let text: String
    let sourceDevice: String
    let userId: String
}

struct CommandResult: Codable {
    let requestId: String
    let status: String
    let message: String
    let requiresApproval: Bool
}

final class CommandClient {
    private let baseURL: URL
    private let session: URLSession

    init(baseURL: URL, session: URLSession = .shared) {
        self.baseURL = baseURL
        self.session = session
    }

    func send(_ request: CommandRequest) async throws -> CommandResult {
        var urlRequest = URLRequest(url: baseURL.appendingPathComponent("commands"))
        urlRequest.httpMethod = "POST"
        urlRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")
        urlRequest.httpBody = try JSONEncoder().encode(request)

        let (data, response) = try await session.data(for: urlRequest)
        guard let http = response as? HTTPURLResponse, 200..<300 ~= http.statusCode else {
            throw URLError(.badServerResponse)
        }
        return try JSONDecoder().decode(CommandResult.self, from: data)
    }
}
