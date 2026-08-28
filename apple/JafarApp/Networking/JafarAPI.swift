import Combine
import Foundation

struct DashboardMatter: Codable, Identifiable, Sendable {
    let id: String
    let title: String
    let status: String
    let matterType: String
    let clientName: String?
    let caseNumber: String?
    let deadlineCount: Int
    let overdueDeadlineCount: Int
    let nextDeadlineTitle: String?
    let nextDeadlineDate: String?
}

struct DashboardSignal: Codable, Identifiable, Sendable {
    let id: String
    let kind: String
    let title: String
    let body: String
    let priority: Int
    let requiresApproval: Bool
    let matterId: String?
    let dueDate: String?
}

struct DashboardSnapshot: Codable, Sendable {
    let generatedAt: String
    let totalMatters: Int
    let activeMatters: Int
    let overdueDeadlines: Int
    let deadlinesNext7Days: Int
    let pendingApprovals: Int
    let matters: [DashboardMatter]
    let signals: [DashboardSignal]

    static let empty = DashboardSnapshot(
        generatedAt: "",
        totalMatters: 0,
        activeMatters: 0,
        overdueDeadlines: 0,
        deadlinesNext7Days: 0,
        pendingApprovals: 0,
        matters: [],
        signals: []
    )
}

protocol DashboardClient: Sendable {
    func fetchDashboard() async throws -> DashboardSnapshot
}

struct LocalDashboardClient: DashboardClient {
    func fetchDashboard() async throws -> DashboardSnapshot {
        .empty
    }
}

struct RemoteDashboardClient: DashboardClient {
    let endpoint: URL
    let session: URLSession
    let authorizationToken: String?

    init(
        endpoint: URL,
        session: URLSession = .shared,
        authorizationToken: String? = nil
    ) {
        self.endpoint = endpoint
        self.session = session
        self.authorizationToken = authorizationToken
    }

    func fetchDashboard() async throws -> DashboardSnapshot {
        var request = URLRequest(url: endpoint)
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
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        return try decoder.decode(DashboardSnapshot.self, from: data)
    }
}

enum JafarAPIConfiguration {
    static var baseURL: URL? {
        if let environment = ProcessInfo.processInfo.environment["JAFAR_API_BASE_URL"],
           let url = URL(string: environment),
           !environment.isEmpty {
            return url
        }
        if let configured = Bundle.main.object(forInfoDictionaryKey: "JafarAPIBaseURL") as? String,
           let url = URL(string: configured),
           !configured.isEmpty {
            return url
        }
        return nil
    }

    static var authorizationToken: String? {
        ProcessInfo.processInfo.environment["JAFAR_API_TOKEN"]
    }
}

enum JafarClientFactory {
    static func commandClient() -> any CommandClient {
        guard let baseURL = JafarAPIConfiguration.baseURL else {
            return LocalCommandClient()
        }
        return RemoteCommandClient(
            endpoint: baseURL.appendingPathComponent("v1/command"),
            authorizationToken: JafarAPIConfiguration.authorizationToken
        )
    }

    static func dashboardClient() -> any DashboardClient {
        guard let baseURL = JafarAPIConfiguration.baseURL else {
            return LocalDashboardClient()
        }
        return RemoteDashboardClient(
            endpoint: baseURL.appendingPathComponent("v1/dashboard"),
            authorizationToken: JafarAPIConfiguration.authorizationToken
        )
    }
}

@MainActor
final class DashboardStore: ObservableObject {
    @Published private(set) var snapshot = DashboardSnapshot.empty
    @Published private(set) var isLoading = false
    @Published private(set) var errorMessage: String?

    private let client: any DashboardClient

    init(client: any DashboardClient) {
        self.client = client
    }

    func refresh() async {
        guard !isLoading else { return }
        isLoading = true
        defer { isLoading = false }
        do {
            snapshot = try await client.fetchDashboard()
            errorMessage = nil
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}

enum JafarAPIError: Error, Sendable {
    case invalidResponse
    case httpStatus(Int)
}
