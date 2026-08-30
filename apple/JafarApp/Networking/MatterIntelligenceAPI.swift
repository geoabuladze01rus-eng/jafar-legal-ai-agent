import Foundation

struct IntelligenceSource: Codable, Sendable {
    let source: String
    let available: Bool
}

struct MatterDocumentProjection: Codable, Identifiable, Sendable {
    let id: String
    let filename: String
    let documentType: String
    let status: String
    let analysisStatus: String
    let createdAt: Date
    let provenance: String
}

struct MatterEvidenceProjection: Codable, Identifiable, Sendable {
    let id: String
    let summary: String
    let sourceDocumentId: String?
    let pageOrFragment: String?
    let supports: String?
    let confidence: Double
    let verificationState: String
}

struct MatterTimelineProjection: Codable, Identifiable, Sendable {
    let id: String
    let eventAt: Date
    let event: String
    let source: String?
    let confidence: Double
    let verificationState: String
}

struct MatterContradictionProjection: Codable, Identifiable, Sendable {
    let id: String
    let statementA: String
    let sourceA: String?
    let statementB: String
    let sourceB: String?
    let category: String
    let significance: String
    let confidence: Double
    let verificationState: String
}

struct MatterAuthorityProjection: Codable, Identifiable, Sendable {
    let id: String
    let court: String
    let date: String?
    let number: String?
    let documentType: String?
    let sourceKind: String
    let verificationState: String
    let holding: String?
    let applicability: String?
    let freshness: String?
    let sourceURL: URL?
}

struct MatterCouncilProjection: Codable, Sendable {
    let participatingModels: [String]
    let conclusions: [String]
    let unresolvedIssues: [String]
    let available: Bool
    let verificationState: String
}

struct MatterPositionProjection: Codable, Sendable {
    let draft: String?
    let state: String
    let reviewed: Bool
    let lawyerApproved: Bool
}

struct MatterHearingProjection: Codable, Sendable {
    let goal: String?
    let theses: [String]
    let questions: [String]
    let documents: [String]
    let available: Bool
}

struct MatterCostProjection: Codable, Sendable {
    let todayUSD: Double
    let monthUSD: Double
    let reservedUSD: Double
    let settledUSD: Double
    let remainingUSD: Double?
}

struct MatterIntelligenceEnvelope<T: Codable & Sendable>: Codable, Sendable {
    let matterID: String
    let source: IntelligenceSource
    let items: [T]
}

protocol MatterIntelligenceClient: Sendable {
    func documents(matterID: String, limit: Int) async throws -> MatterIntelligenceEnvelope<MatterDocumentProjection>
    func evidence(matterID: String, limit: Int) async throws -> MatterIntelligenceEnvelope<MatterEvidenceProjection>
    func timeline(matterID: String, limit: Int) async throws -> MatterIntelligenceEnvelope<MatterTimelineProjection>
    func contradictions(matterID: String, limit: Int) async throws -> MatterIntelligenceEnvelope<MatterContradictionProjection>
    func authorities(matterID: String, limit: Int) async throws -> MatterIntelligenceEnvelope<MatterAuthorityProjection>
}

struct RemoteMatterIntelligenceClient: MatterIntelligenceClient {
    let baseURL: URL
    let session: URLSession
    let authorizationToken: String?

    init(baseURL: URL, session: URLSession = .shared, authorizationToken: String? = nil) {
        self.baseURL = baseURL
        self.session = session
        self.authorizationToken = authorizationToken
    }

    func documents(matterID: String, limit: Int = 50) async throws -> MatterIntelligenceEnvelope<MatterDocumentProjection> {
        try await fetch(path: "documents", matterID: matterID, limit: limit)
    }

    func evidence(matterID: String, limit: Int = 50) async throws -> MatterIntelligenceEnvelope<MatterEvidenceProjection> {
        try await fetch(path: "evidence", matterID: matterID, limit: limit)
    }

    func timeline(matterID: String, limit: Int = 50) async throws -> MatterIntelligenceEnvelope<MatterTimelineProjection> {
        try await fetch(path: "timeline", matterID: matterID, limit: limit)
    }

    func contradictions(matterID: String, limit: Int = 50) async throws -> MatterIntelligenceEnvelope<MatterContradictionProjection> {
        try await fetch(path: "contradictions", matterID: matterID, limit: limit)
    }

    func authorities(matterID: String, limit: Int = 50) async throws -> MatterIntelligenceEnvelope<MatterAuthorityProjection> {
        try await fetch(path: "authorities", matterID: matterID, limit: limit)
    }

    private func fetch<T: Codable & Sendable>(path: String, matterID: String, limit: Int) async throws -> MatterIntelligenceEnvelope<T> {
        var components = URLComponents(url: baseURL.appendingPathComponent("v1/matters/\(matterID)/intelligence/\(path)"), resolvingAgainstBaseURL: false)
        components?.queryItems = [URLQueryItem(name: "limit", value: String(min(max(limit, 1), 100)))]
        guard let url = components?.url else { throw JafarAPIError.invalidResponse }
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        if let authorizationToken, !authorizationToken.isEmpty { request.setValue("Bearer \(authorizationToken)", forHTTPHeaderField: "Authorization") }
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else { throw JafarAPIError.invalidResponse }
        guard (200...299).contains(http.statusCode) else { throw JafarAPIError.httpStatus(http.statusCode) }
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        decoder.dateDecodingStrategy = .iso8601
        return try decoder.decode(MatterIntelligenceEnvelope<T>.self, from: data)
    }
}

