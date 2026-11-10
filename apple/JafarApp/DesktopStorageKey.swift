#if os(macOS)
import Foundation
import Security

enum DesktopStorageKeyError: Error {
    case keychainUnavailable
    case invalidStoredKey
    case randomGenerationFailed
    case existingEncryptedArchiveRequiresRecovery
}

struct DesktopStorageKey {
    private let service = "ru.jafar.legal-ai.desktop-storage"
    private let account = "master-key-v1"

    func loadOrCreate() throws -> String {
        if let existing = try read() {
            guard existing.count == 32 else { throw DesktopStorageKeyError.invalidStoredKey }
            return existing.base64URLEncodedString()
        }
        // Never silently generate a replacement key if encrypted files already
        // exist. Without this guard a missing Keychain entry could make an
        // otherwise recoverable local archive appear permanently unreadable.
        guard !hasExistingEncryptedArchive() else {
            throw DesktopStorageKeyError.existingEncryptedArchiveRequiresRecovery
        }
        var bytes = [UInt8](repeating: 0, count: 32)
        guard SecRandomCopyBytes(kSecRandomDefault, bytes.count, &bytes) == errSecSuccess else {
            throw DesktopStorageKeyError.randomGenerationFailed
        }
        let key = Data(bytes)
        try save(key)
        return key.base64URLEncodedString()
    }

    private func hasExistingEncryptedArchive() -> Bool {
        let root: URL
        if let custom = ProcessInfo.processInfo.environment["JAFAR_DESKTOP_HOME"],
           !custom.isEmpty {
            root = URL(fileURLWithPath: custom, isDirectory: true)
        } else {
            root = FileManager.default.homeDirectoryForCurrentUser
                .appendingPathComponent("Library/Application Support/JAFAR", isDirectory: true)
        }
        let manager = FileManager.default
        let databases = [
            "matters.sqlite3",
            "corpus.sqlite3",
            "drafts.sqlite3",
            "claim-review-decisions.sqlite3"
        ]
        if databases.contains(where: {
            manager.fileExists(atPath: root.appendingPathComponent($0).path)
        }) {
            return true
        }
        let documents = root.appendingPathComponent("documents", isDirectory: true)
        if let entries = try? manager.contentsOfDirectory(
            at: documents, includingPropertiesForKeys: nil
        ) {
            return entries.contains(where: { $0.pathExtension == "jafarblob" })
        }
        return false
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
