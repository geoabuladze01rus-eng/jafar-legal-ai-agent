import Foundation

struct SyncPushResponse: Codable, Sendable {
    let accepted: Int
    let changes: [RemoteSyncChange]
}

struct RemoteSyncChange: Codable, Sendable {
    let entityType: String
    let entityId: String
    let version: Int64
    let updatedAt: Date
}

struct SupabaseSyncTransport {
    let functionURL: URL
    let accessTokenProvider: @Sendable () async throws -> String

    func push(_ envelopes: [SyncEnvelope]) async throws -> SyncPushResponse {
        guard !envelopes.isEmpty else {
            return SyncPushResponse(accepted: 0, changes: [])
        }

        var request = URLRequest(url: functionURL)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("Bearer \(try await accessTokenProvider())", forHTTPHeaderField: "Authorization")
        request.httpBody = try JSONEncoder().encode(["envelopes": envelopes])

        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse, (200..<300).contains(http.statusCode) else {
            throw URLError(.badServerResponse)
        }
        return try JSONDecoder().decode(SyncPushResponse.self, from: data)
    }
}
