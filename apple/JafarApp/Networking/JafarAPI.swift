import Combine
import Foundation
import Security

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
    private static let baseURLDefaultsKey = "jafar.api.base_url"

    static var baseURL: URL? {
        if let saved = UserDefaults.standard.string(forKey: baseURLDefaultsKey),
           let url = URL(string: saved),
           !saved.isEmpty {
            return url
        }
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

    static var baseURLString: String {
        UserDefaults.standard.string(forKey: baseURLDefaultsKey) ?? baseURL?.absoluteString ?? ""
    }

    static var authorizationToken: String? {
        JafarCredentialStore.readToken()
            ?? ProcessInfo.processInfo.environment["JAFAR_API_TOKEN"]
    }

    static func save(baseURLString: String, token: String) throws {
        let normalized = baseURLString.trimmingCharacters(in: .whitespacesAndNewlines)
        if normalized.isEmpty {
            UserDefaults.standard.removeObject(forKey: baseURLDefaultsKey)
        } else {
            UserDefaults.standard.set(normalized, forKey: baseURLDefaultsKey)
        }

        let normalizedToken = token.trimmingCharacters(in: .whitespacesAndNewlines)
        if normalizedToken.isEmpty {
            try JafarCredentialStore.deleteToken()
        } else {
            try JafarCredentialStore.saveToken(normalizedToken)
        }
    }

    static func disableRemoteMode() throws {
        UserDefaults.standard.removeObject(forKey: baseURLDefaultsKey)
        try JafarCredentialStore.deleteToken()
    }
}

enum JafarCredentialStore {
    private static let account = "jafar-api-token"
    private static var service: String {
        Bundle.main.bundleIdentifier ?? "ru.jafar.legal-ai"
    }

    static func readToken() -> String? {
        var query = baseQuery
        query[kSecReturnData as String] = true
        query[kSecMatchLimit as String] = kSecMatchLimitOne

        var result: CFTypeRef?
        let status = SecItemCopyMatching(query as CFDictionary, &result)
        if status == errSecItemNotFound {
            return nil
        }
        guard status == errSecSuccess,
              let data = result as? Data,
              let value = String(data: data, encoding: .utf8) else {
            return nil
        }
        return value
    }

    static func saveToken(_ token: String) throws {
        let data = Data(token.utf8)
        let update = [kSecValueData as String: data]
        let updateStatus = SecItemUpdate(
            baseQuery as CFDictionary,
            update as CFDictionary
        )
        if updateStatus == errSecSuccess {
            return
        }
        guard updateStatus == errSecItemNotFound else {
            throw JafarAPIError.keychain(updateStatus)
        }

        var create = baseQuery
        create[kSecValueData as String] = data
        let createStatus = SecItemAdd(create as CFDictionary, nil)
        guard createStatus == errSecSuccess else {
            throw JafarAPIError.keychain(createStatus)
        }
    }

    static func deleteToken() throws {
        let status = SecItemDelete(baseQuery as CFDictionary)
        guard status == errSecSuccess || status == errSecItemNotFound else {
            throw JafarAPIError.keychain(status)
        }
    }

    private static var baseQuery: [String: Any] {
        [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
        ]
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

    private var client: any DashboardClient

    init(client: any DashboardClient) {
        self.client = client
    }

    func reconfigure(client: any DashboardClient) {
        self.client = client
        snapshot = .empty
        errorMessage = nil
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
    case keychain(OSStatus)
}
