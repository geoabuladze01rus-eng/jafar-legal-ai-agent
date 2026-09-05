#if os(macOS)
import Foundation
import Security

enum DesktopStorageKeyError: Error {
    case keychainUnavailable
    case invalidStoredKey
    case randomGenerationFailed
}

struct DesktopStorageKey {
    private let service = "ru.jafar.legal-ai.desktop-storage"
    private let account = "master-key-v1"

    func loadOrCreate() throws -> String {
        if let existing = try read() {
            guard existing.count == 32 else { throw DesktopStorageKeyError.invalidStoredKey }
            return existing.base64URLEncodedString()
        }
        var bytes = [UInt8](repeating: 0, count: 32)
        guard SecRandomCopyBytes(kSecRandomDefault, bytes.count, &bytes) == errSecSuccess else {
            throw DesktopStorageKeyError.randomGenerationFailed
        }
        let key = Data(bytes)
        try save(key)
        return key.base64URLEncodedString()
    }

    private func read() throws -> Data? {
        var query = baseQuery
        query[kSecReturnData as String] = true
        query[kSecMatchLimit as String] = kSecMatchLimitOne
        var item: CFTypeRef?
        let status = SecItemCopyMatching(query as CFDictionary, &item)
        if status == errSecItemNotFound { return nil }
        guard status == errSecSuccess, let data = item as? Data else {
            throw DesktopStorageKeyError.keychainUnavailable
        }
        return data
    }

    private func save(_ key: Data) throws {
        var attributes = baseQuery
        attributes[kSecValueData as String] = key
        attributes[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
        let status = SecItemAdd(attributes as CFDictionary, nil)
        guard status == errSecSuccess else { throw DesktopStorageKeyError.keychainUnavailable }
    }

    private var baseQuery: [String: Any] {
        [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
        ]
    }
}

private extension Data {
    func base64URLEncodedString() -> String {
        base64EncodedString()
            .replacingOccurrences(of: "+", with: "-")
            .replacingOccurrences(of: "/", with: "_")
            .replacingOccurrences(of: "=", with: "")
    }
}
#endif
