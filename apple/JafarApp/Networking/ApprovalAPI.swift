import Combine
import Foundation

struct ApprovalItem: Codable, Identifiable, Sendable {
    var id: String { actionId }

    let actionId: String
    let actionType: String
    let description: String
    let requestedBy: String
    let state: String
    let evidenceIds: [String]
    let payloadBound: Bool
    let createdAt: String
    let decidedAt: String?
    let decidedBy: String?
    let decisionReason: String?
    let executedAt: String?
}

struct ApprovalDecision: Codable, Sendable {
    let actionId: String
    let state: String
    let decidedBy: String
    let decidedAt: String
    let reason: String?
}

private struct ApprovalDecisionBody: Encodable {
    let reason: String?
}

protocol ApprovalClient: Sendable {
    func fetchPending() async throws -> [ApprovalItem]
    func fetchApprovedAwaitingExecution() async throws -> [ApprovalItem]
    func approve(actionId: String) async throws -> ApprovalDecision
    func reject(actionId: String, reason: String) async throws -> ApprovalDecision
}

struct LocalApprovalClient: ApprovalClient {
    func fetchPending() async throws -> [ApprovalItem] { [] }

    func fetchApprovedAwaitingExecution() async throws -> [ApprovalItem] { [] }

    func approve(actionId: String) async throws -> ApprovalDecision {
        throw JafarAPIError.httpStatus(503)
    }

    func reject(actionId: String, reason: String) async throws -> ApprovalDecision {
        throw JafarAPIError.httpStatus(503)
    }
}

struct RemoteApprovalClient: ApprovalClient {
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

    func fetchPending() async throws -> [ApprovalItem] {
        try await fetch(state: "proposed")
    }

    func fetchApprovedAwaitingExecution() async throws -> [ApprovalItem] {
        try await fetch(state: "approved")
    }

    func approve(actionId: String) async throws -> ApprovalDecision {
        try await decide(
            actionId: actionId,
            operation: "approve",
            body: ApprovalDecisionBody(reason: nil)
        )
    }

    func reject(actionId: String, reason: String) async throws -> ApprovalDecision {
        try await decide(
            actionId: actionId,
            operation: "reject",
            body: ApprovalDecisionBody(reason: reason)
        )
    }

    private func fetch(state: String) async throws -> [ApprovalItem] {
        var components = URLComponents(
            url: baseURL.appendingPathComponent("v1/approvals"),
            resolvingAgainstBaseURL: false
        )
        components?.queryItems = [URLQueryItem(name: "state", value: state)]
        guard let url = components?.url else {
            throw JafarAPIError.invalidResponse
        }
        var request = authorizedRequest(url: url, method: "GET")
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        let data = try await perform(request)
        return try decoder.decode([ApprovalItem].self, from: data)
    }

    private func decide(
        actionId: String,
        operation: String,
        body: ApprovalDecisionBody
    ) async throws -> ApprovalDecision {
        let url = baseURL
            .appendingPathComponent("v1/approvals")
            .appendingPathComponent(actionId)
            .appendingPathComponent(operation)
        var request = authorizedRequest(url: url, method: "POST")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(body)
        let data = try await perform(request)
        return try decoder.decode(ApprovalDecision.self, from: data)
    }

    private func authorizedRequest(url: URL, method: String) -> URLRequest {
        var request = URLRequest(url: url)
        request.httpMethod = method
        if let authorizationToken, !authorizationToken.isEmpty {
            request.setValue(
                "Bearer \(authorizationToken)",
                forHTTPHeaderField: "Authorization"
            )
        }
        return request
    }

    private func perform(_ request: URLRequest) async throws -> Data {
        let (data, response) = try await session.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse else {
            throw JafarAPIError.invalidResponse
        }
        guard (200...299).contains(httpResponse.statusCode) else {
            throw JafarAPIError.httpStatus(httpResponse.statusCode)
        }
        return data
    }

    private var decoder: JSONDecoder {
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        return decoder
    }
}

extension JafarClientFactory {
    static func approvalClient() -> any ApprovalClient {
        guard let baseURL = JafarAPIConfiguration.baseURL else {
            return LocalApprovalClient()
        }
        return RemoteApprovalClient(
            baseURL: baseURL,
            authorizationToken: JafarAPIConfiguration.authorizationToken
        )
    }
}

@MainActor
final class ApprovalStore: ObservableObject {
    @Published private(set) var pending: [ApprovalItem] = []
    @Published private(set) var approvedAwaitingExecution: [ApprovalItem] = []
    @Published private(set) var isLoading = false
    @Published private(set) var processingIDs: Set<String> = []
    @Published private(set) var errorMessage: String?

    private var client: any ApprovalClient

    init(client: any ApprovalClient) {
        self.client = client
    }

    func reconfigure(client: any ApprovalClient) {
        self.client = client
        pending = []
        approvedAwaitingExecution = []
        processingIDs = []
        errorMessage = nil
    }

    func refresh() async {
        guard !isLoading else { return }
        isLoading = true
        defer { isLoading = false }
        do {
            async let pendingRequest = client.fetchPending()
            async let approvedRequest = client.fetchApprovedAwaitingExecution()
            pending = try await pendingRequest
            approvedAwaitingExecution = try await approvedRequest
            if pending.contains(where: { !$0.payloadBound }) {
                errorMessage = "Есть старый запрос без зафиксированного payload. Его нельзя одобрить безопасно."
            } else if approvedAwaitingExecution.contains(where: { !$0.payloadBound }) {
                errorMessage = "Есть старое одобрение без payload binding. Его выполнение заблокировано."
            } else {
                errorMessage = nil
            }
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func approve(_ item: ApprovalItem) async -> Bool {
        guard item.payloadBound else {
            errorMessage = "Одобрение заблокировано: точное содержимое действия не зафиксировано."
            return false
        }
        return await decide(item: item) {
            try await client.approve(actionId: item.actionId)
        }
    }

    func reject(_ item: ApprovalItem, reason: String) async -> Bool {
        await decide(item: item) {
            try await client.reject(actionId: item.actionId, reason: reason)
        }
    }

    private func decide(
        item: ApprovalItem,
        operation: () async throws -> ApprovalDecision
    ) async -> Bool {
        guard !processingIDs.contains(item.id) else { return false }
        processingIDs.insert(item.id)
        defer { processingIDs.remove(item.id) }
        do {
            _ = try await operation()
            pending.removeAll { $0.id == item.id }
            errorMessage = nil
            return true
        } catch {
            errorMessage = error.localizedDescription
            return false
        }
    }
}
