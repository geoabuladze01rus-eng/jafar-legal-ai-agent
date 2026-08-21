import Foundation

@MainActor
final class SupabaseAuditLogger: JafarAuditLogging {
    private let endpoint: URL
    private let session: URLSession
    private let authorizationToken: @Sendable () async throws -> String

    init(
        endpoint: URL,
        session: URLSession = .shared,
        authorizationToken: @escaping @Sendable () async throws -> String
    ) {
        self.endpoint = endpoint
        self.session = session
        self.authorizationToken = authorizationToken
    }

    func record(_ event: JafarAuditEvent) async throws {
        let token = try await authorizationToken()
        var request = URLRequest(url: endpoint)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        request.httpBody = try JSONEncoder.jafarAudit.encode(event)

        let (_, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse, (200..<300).contains(http.statusCode) else {
            throw URLError(.badServerResponse)
        }
    }
}

private extension JSONEncoder {
    static let jafarAudit: JSONEncoder = {
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        return encoder
    }()
}
