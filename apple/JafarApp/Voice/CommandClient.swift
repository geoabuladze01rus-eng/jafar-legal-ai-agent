import Foundation
import Security

struct CommandRequest: Codable, Sendable {
    let text: String
    let userId: String
    let sourceDevice: String

    enum CodingKeys: String, CodingKey {
        case text
        case userId = "user_id"
        case sourceDevice = "source_device"
    }
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

enum CommandClientError: Error, Sendable, LocalizedError {
    case invalidResponse
    case httpStatus(Int)

    var errorDescription: String? {
        switch self {
        case .invalidResponse:
            return "API вернул некорректный ответ."
        case let .httpStatus(statusCode):
            return "API вернул HTTP \(statusCode)."
        }
    }
}

enum JafarClientConfiguration {
    private static let endpointDefaultsKey = "jafar.api.endpoint"
    private static let keychainService = "com.jafar.legal-ai-agent"
    private static let keychainAccount = "api-key"

    static var endpointString: String {
        UserDefaults.standard.string(forKey: endpointDefaultsKey) ?? ""
    }

    static func configuredRemoteClient() -> RemoteCommandClient? {
        guard
            let endpoint = validatedEndpoint(endpointString),
            let apiKey = readAPIKey(),
            !apiKey.isEmpty
        else {
            return nil
        }
        return RemoteCommandClient(endpoint: endpoint, apiKey: apiKey)
    }

    static func makeCommandClient() -> any CommandClient {
        configuredRemoteClient() ?? LocalCommandClient()
    }

    static func save(endpoint: String, apiKey: String?) throws {
        guard let validated = validatedEndpoint(endpoint) else {
            throw JafarConfigurationError.invalidEndpoint
        }
        UserDefaults.standard.set(validated.absoluteString, forKey: endpointDefaultsKey)
        if let apiKey, !apiKey.isEmpty {
            try saveAPIKey(apiKey)
        }
    }

    static func clearAPIKey() {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: keychainService,
            kSecAttrAccount as String: keychainAccount,
        ]
        SecItemDelete(query as CFDictionary)
    }

    private static func validatedEndpoint(_ rawValue: String) -> URL? {
        guard
            let url = URL(string: rawValue.trimmingCharacters(in: .whitespacesAndNewlines)),
            let scheme = url.scheme?.lowercased(),
            ["http", "https"].contains(scheme),
            url.host != nil
        else {
            return nil
        }
        return url
    }

    private static func saveAPIKey(_ apiKey: String) throws {
        let encoded = Data(apiKey.utf8)
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: keychainService,
            kSecAttrAccount as String: keychainAccount,
        ]

        let updateStatus = SecItemUpdate(
            query as CFDictionary,
            [kSecValueData as String: encoded] as CFDictionary
        )
        if updateStatus == errSecSuccess {
            return
        }
        guard updateStatus == errSecItemNotFound else {
            throw JafarConfigurationError.keychain(updateStatus)
        }

        var insert = query
        insert[kSecValueData as String] = encoded
        insert[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
        let status = SecItemAdd(insert as CFDictionary, nil)
        guard status == errSecSuccess else {
            throw JafarConfigurationError.keychain(status)
        }
    }

    private static func readAPIKey() -> String? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: keychainService,
            kSecAttrAccount as String: keychainAccount,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne,
        ]
        var result: CFTypeRef?
        guard SecItemCopyMatching(query as CFDictionary, &result) == errSecSuccess,
              let data = result as? Data
        else {
            return nil
        }
        return String(data: data, encoding: .utf8)
    }
}

enum JafarConfigurationError: Error, LocalizedError {
    case invalidEndpoint
    case keychain(OSStatus)

    var errorDescription: String? {
        switch self {
        case .invalidEndpoint:
            return "Укажите полный адрес API, например http://127.0.0.1:8000/v1/command."
        case let .keychain(status):
            return "Не удалось сохранить API-ключ в Keychain (\(status))."
        }
    }
}
