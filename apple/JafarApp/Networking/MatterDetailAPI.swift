import Foundation

struct MatterDeadline: Codable, Identifiable, Sendable {
    var id: String { "\(title)|\(dueDate ?? "")|\(sourceText ?? "")" }

    let title: String
    let dueDate: String?
    let sourceText: String?
    let confidence: Double
}

struct MatterDetail: Codable, Identifiable, Sendable {
    let id: String
    let title: String
    let matterType: String
    let clientName: String?
    let opposingParty: String?
    let courtOrAuthority: String?
    let caseNumber: String?
    let status: String
    let deadlines: [MatterDeadline]
    let createdAt: String
    let updatedAt: String
}

struct MatterTimelineEvent: Codable, Identifiable, Sendable {
    let id: String
    let matterId: String
    let title: String
    let eventDate: String
    let description: String?
    let sourceDocument: String?
    let documentFingerprint: String?
    let createdAt: String
}

struct MatterWorkspaceSnapshot: Sendable {
    let matter: MatterDetail
    let events: [MatterTimelineEvent]
}

protocol MatterDetailClient: Sendable {
    func fetchMatter(_ matterId: String) async throws -> MatterWorkspaceSnapshot
}

struct LocalMatterDetailClient: MatterDetailClient {
    func fetchMatter(_ matterId: String) async throws -> MatterWorkspaceSnapshot {
        throw JafarAPIError.httpStatus(503)
    }
}

struct RemoteMatterDetailClient: MatterDetailClient {
    let baseURL: URL
    let session: URLSession
    let authorizationToken: String?

    init(
        baseURL: URL,
        session: URLSession = .shared,
        authorizationToken: String? = nil
    ) {
        self.baseURL = baseURL
        self.session = session
        self.authorizationToken = authorizationToken
    }

    func fetchMatter(_ matterId: String) async throws -> MatterWorkspaceSnapshot {
        let encodedId = matterId.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed)
            ?? matterId
        let matterURL = baseURL
            .appendingPathComponent("v1/matters")
            .appendingPathComponent(encodedId)
        let eventsURL = matterURL.appendingPathComponent("events")

        async let matterData = perform(url: matterURL)
        async let eventData = perform(url: eventsURL)

        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        let matter = try decoder.decode(MatterDetail.self, from: await matterData)
        let events = try decoder.decode([MatterTimelineEvent].self, from: await eventData)
        return MatterWorkspaceSnapshot(matter: matter, events: events)
    }

    private func perform(url: URL) async throws -> Data {
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        if let authorizationToken, !authorizationToken.isEmpty {
            request.setValue("Bearer \(authorizationToken)", forHTTPHeaderField: "Authorization")
        }
        let (data, response) = try await session.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse else {
            throw JafarAPIError.invalidResponse
        }
        guard (200...299).contains(httpResponse.statusCode) else {
            throw JafarAPIError.httpStatus(httpResponse.statusCode)
        }
        return data
    }
}

extension JafarClientFactory {
    static func matterDetailClient() -> any MatterDetailClient {
        guard let baseURL = JafarAPIConfiguration.baseURL else {
            return LocalMatterDetailClient()
        }
        return RemoteMatterDetailClient(
            baseURL: baseURL,
            authorizationToken: JafarAPIConfiguration.authorizationToken
        )
    }
}
