#!/usr/bin/env swift
// JAFAR 2.1 beta: explicit OFFLINE Keychain recovery kit.
//
// The sealed kit holds the original 32-byte desktop master key.
// It MUST be stored separately from encrypted client backups. Never upload it
// to messaging apps, source repositories, logs or cloud drives.
#if os(macOS)
import Foundation
import CryptoKit
import CommonCrypto
import Darwin
import Security

private let serviceName = "ru.jafar.legal-ai.desktop-storage"
private let accountName = "master-key-v1"
private let formatName = "JAFAR-MAC-KEY-RECOVERY"
private let versionNumber = 1
private let iterations: UInt32 = 600_000
private let aad = Data("JAFAR-KEY-RECOVERY-V1".utf8)

private enum RecoveryError: Error, CustomStringConvertible {
    case invalidCommand
    case needsTerminal
    case invalidPassword
    case invalidFile
    case cryptography
    case missingKey
    case keyAlreadyExists
    case keychain(Int32)
    case applicationOpen
    case unsafeTarget

    var description: String {
        switch self {
        case .invalidCommand: return "Invalid command or arguments."
        case .needsTerminal: return "An interactive terminal is required; passwords must not appear in arguments."
        case .invalidPassword: return "Passphrase must contain at least 20 characters; both entries must match."
        case .invalidFile: return "Recovery kit is invalid, damaged, unsupported, or authenticated data is incorrect."
        case .cryptography: return "Recovery encryption or authentication failed."
        case .missingKey: return "Desktop master key does not exist in this Keychain."
        case .keyAlreadyExists: return "Keychain master key already exists; refusing to replace it."
        case .keychain(let status): return "Keychain operation failed (status \(status))."
        case .applicationOpen: return "Quit JAFAR and its local backend before using the recovery utility."
        case .unsafeTarget: return "Destination exists, is a link, or cannot be safely created."
        }
    }
}

private struct RecoveryEnvelope: Codable {
    let format: String
    let version: Int
    let kdf: String
    let rounds: UInt32
    let salt: String
    let sealed: String
}

private func randomBytes(_ count: Int) throws -> Data {
    var bytes = [UInt8](repeating: 0, count: count)
    guard SecRandomCopyBytes(kSecRandomDefault, count, &bytes) == errSecSuccess else {
        throw RecoveryError.cryptography
    }
    return Data(bytes)
}

private func deriveKey(passphrase: String, salt: Data) throws -> SymmetricKey {
    guard passphrase.count >= 20 && salt.count == 16 else {
        throw RecoveryError.invalidPassword
    }
    var bytes = [UInt8](repeating: 0, count: 32)
    let status = salt.withUnsafeBytes { rawSalt in
        passphrase.withCString { password in
            CCKeyDerivationPBKDF(
                CCPBKDFAlgorithm(kCCPBKDF2),
                password,
                passphrase.utf8.count,
                rawSalt.bindMemory(to: UInt8.self).baseAddress,
                salt.count,
                CCPseudoRandomAlgorithm(kCCPRFHmacAlgSHA256),
                iterations,
                &bytes,
                bytes.count
            )
        }
    }
    guard status == kCCSuccess else { throw RecoveryError.cryptography }
    defer {
        for index in bytes.indices { bytes[index] = 0 }
    }
    return SymmetricKey(data: Data(bytes))
}

private func makeEnvelope(masterKey: Data, passphrase: String) throws -> Data {
    guard masterKey.count == 32 else { throw RecoveryError.invalidFile }
    let salt = try randomBytes(16)
    let derived = try deriveKey(passphrase: passphrase, salt: salt)
    let sealed = try AES.GCM.seal(masterKey, using: derived, authenticating: aad)
    guard let combined = sealed.combined else { throw RecoveryError.cryptography }
    return try JSONEncoder().encode(
        RecoveryEnvelope(
            format: formatName,
            version: versionNumber,
            kdf: "PBKDF2-HMAC-SHA256",
            rounds: iterations,
            salt: salt.base64EncodedString(),
            sealed: combined.base64EncodedString()
        )
    )
}

private func openEnvelope(_ data: Data, passphrase: String) throws -> Data {
    guard data.count <= 4096,
          let info = try? JSONDecoder().decode(RecoveryEnvelope.self, from: data),
          info.format == formatName,
          info.version == versionNumber,
          info.kdf == "PBKDF2-HMAC-SHA256",
          info.rounds == iterations,
          let salt = Data(base64Encoded: info.salt),
          salt.count == 16,
          let combined = Data(base64Encoded: info.sealed),
          combined.count == 60 else {
        throw RecoveryError.invalidFile
    }
    let derived = try deriveKey(passphrase: passphrase, salt: salt)
    do {
        let box = try AES.GCM.SealedBox(combined: combined)
        let plaintext = try AES.GCM.open(box, using: derived, authenticating: aad)
        guard plaintext.count == 32 else { throw RecoveryError.invalidFile }
        return plaintext
    } catch {
        throw RecoveryError.cryptography
    }
}

private func readMasterKey() throws -> Data? {
    let query: [String: Any] = [
        kSecClass as String: kSecClassGenericPassword,
        kSecAttrService as String: serviceName,
        kSecAttrAccount as String: accountName,
        kSecReturnData as String: true,
        kSecMatchLimit as String: kSecMatchLimitOne,
    ]
    var item: CFTypeRef?
    let status = SecItemCopyMatching(query as CFDictionary, &item)
    if status == errSecItemNotFound { return nil }
    guard status == errSecSuccess, let data = item as? Data, data.count == 32 else {
        throw RecoveryError.keychain(status)
    }
    return data
}

private func installMasterKey(_ data: Data) throws {
    guard data.count == 32 else { throw RecoveryError.invalidFile }
    guard try readMasterKey() == nil else { throw RecoveryError.keyAlreadyExists }
    let query: [String: Any] = [
        kSecClass as String: kSecClassGenericPassword,
        kSecAttrService as String: serviceName,
        kSecAttrAccount as String: accountName,
        kSecValueData as String: data,
        kSecAttrAccessible as String: kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly,
    ]
    let status = SecItemAdd(query as CFDictionary, nil)
    if status == errSecDuplicateItem { throw RecoveryError.keyAlreadyExists }
    guard status == errSecSuccess else { throw RecoveryError.keychain(status) }
}

private func askSecret(_ prompt: String) throws -> String {
    guard isatty(STDIN_FILENO) == 1 else { throw RecoveryError.needsTerminal }
    var old = termios()
    guard tcgetattr(STDIN_FILENO, &old) == 0 else { throw RecoveryError.needsTerminal }
    var hidden = old
    hidden.c_lflag &= ~tcflag_t(ECHO)
    guard tcsetattr(STDIN_FILENO, TCSANOW, &hidden) == 0 else {
        throw RecoveryError.needsTerminal
    }
    defer {
        _ = tcsetattr(STDIN_FILENO, TCSANOW, &old)
        FileHandle.standardError.write(Data("\n".utf8))
    }
    FileHandle.standardError.write(Data(prompt.utf8))
    var bytes = Data()
    while bytes.count < 4096 {
        let next = FileHandle.standardInput.readData(ofLength: 1)
        guard let ch = next.first else { break }
        if ch == 10 || ch == 13 { break }
        bytes.append(ch)
    }
    guard let result = String(data: bytes, encoding: .utf8),
          result.count >= 20 else { throw RecoveryError.invalidPassword }
    return result
}

private func dataHome() -> URL {
    if let value = ProcessInfo.processInfo.environment["JAFAR_DESKTOP_HOME"],
       !value.isEmpty {
        return URL(fileURLWithPath: value, isDirectory: true)
    }
    return FileManager.default.homeDirectoryForCurrentUser
        .appendingPathComponent("Library/Application Support/JAFAR", isDirectory: true)
}

private func lockedWhileAppClosed<T>(_ action: () throws -> T) throws -> T {
    let home = dataHome()
    var isDirectory: ObjCBool = false
    if !FileManager.default.fileExists(atPath: home.path, isDirectory: &isDirectory) {
        return try action()
    }
    guard isDirectory.boolValue,
          (try? home.resourceValues(forKeys: [.isSymbolicLinkKey]))?.isSymbolicLink != true else {
        throw RecoveryError.unsafeTarget
    }
    let lockPath = home.appendingPathComponent("matters.lock").path
    let fd = open(lockPath, O_RDWR | O_CREAT | O_NOFOLLOW, mode_t(0o600))
    guard fd >= 0 else { throw RecoveryError.unsafeTarget }
    defer { close(fd) }
    guard flock(fd, LOCK_EX | LOCK_NB) == 0 else {
        throw RecoveryError.applicationOpen
    }
    return try action()
}

private func writeNewFile(_ contents: Data, at target: URL) throws {
    let manager = FileManager.default
    guard target.isFileURL, !manager.fileExists(atPath: target.path),
          (try? target.resourceValues(forKeys: [.isSymbolicLinkKey]))?.isSymbolicLink != true else {
        throw RecoveryError.unsafeTarget
    }
    let parent = target.deletingLastPathComponent()
    guard let info = try? parent.resourceValues(forKeys: [.isDirectoryKey, .isSymbolicLinkKey]),
          info.isDirectory == true, info.isSymbolicLink != true else {
        throw RecoveryError.unsafeTarget
    }
    let fd = open(target.path, O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW, mode_t(0o600))
    guard fd >= 0 else { throw RecoveryError.unsafeTarget }
    var successful = false
    defer {
        close(fd)
        if !successful { try? manager.removeItem(at: target) }
    }
    try contents.withUnsafeBytes { raw in
        guard let base = raw.baseAddress else { throw RecoveryError.invalidFile }
        var written = 0
        while written < raw.count {
            let remaining = raw.count - written
            let result = Darwin.write(fd, base.advanced(by: written), remaining)
            guard result > 0 else { throw RecoveryError.unsafeTarget }
            written += result
        }
    }
    guard fsync(fd) == 0 else { throw RecoveryError.unsafeTarget }
    successful = true
}

private func readRecoveryFile(_ file: URL) throws -> Data {
    guard file.isFileURL,
          let resource = try? file.resourceValues(forKeys: [
            .isRegularFileKey, .isSymbolicLinkKey, .fileSizeKey
          ]),
          resource.isRegularFile == true,
          resource.isSymbolicLink != true,
          let size = resource.fileSize, size > 0, size <= 4096 else {
        throw RecoveryError.invalidFile
    }
    return try Data(contentsOf: file)
}

private func selfTest() throws {
    // No Keychain access. Proves round-trip, wrong-secret and ciphertext tampering.
    let key = try randomBytes(32)
    let kit = try makeEnvelope(masterKey: key, passphrase: "synthetic-test-passphrase-12345")
    guard try openEnvelope(kit, passphrase: "synthetic-test-passphrase-12345") == key else {
        throw RecoveryError.cryptography
    }
    var wrongPasswordRejected = false
    do {
        _ = try openEnvelope(kit, passphrase: "incorrect-synthetic-passphrase")
    } catch {
        wrongPasswordRejected = true
    }
    guard wrongPasswordRejected else { throw RecoveryError.cryptography }
    var envelope = try JSONDecoder().decode(RecoveryEnvelope.self, from: kit)
    let damaged = Data(repeating: 0, count: 60)
    envelope = RecoveryEnvelope(
        format: envelope.format, version: envelope.version, kdf: envelope.kdf,
        rounds: envelope.rounds, salt: envelope.salt, sealed: damaged.base64EncodedString()
    )
    var tamperingRejected = false
    do {
        _ = try openEnvelope(
            JSONEncoder().encode(envelope),
            passphrase: "synthetic-test-passphrase-12345"
        )
    } catch {
        tamperingRejected = true
    }
    guard tamperingRejected else { throw RecoveryError.cryptography }
    print("Recovery codec self-test passed; Keychain was not accessed.")
}

private func run() throws {
    let args = Array(CommandLine.arguments.dropFirst())
    if args == ["self-test"] {
        try selfTest()
        return
    }
    if args == ["status"] {
        let exists = try readMasterKey() != nil
        print(exists ? "JAFAR master key exists in the local Keychain." :
            "JAFAR master key is absent. Do not start JAFAR until recovery is complete.")
        return
    }
    guard args.count == 3 else { throw RecoveryError.invalidCommand }
    let command = args[0]
    guard (command == "export" && args[1] == "--output") ||
          (command == "import" && args[1] == "--input") else {
        throw RecoveryError.invalidCommand
    }
    let file = URL(fileURLWithPath: args[2])
    try lockedWhileAppClosed {
        if command == "export" {
            guard let master = try readMasterKey() else { throw RecoveryError.missingKey }
            let password = try askSecret("New independent recovery passphrase (20+ chars): ")
            let confirmation = try askSecret("Confirm recovery passphrase: ")
            guard password == confirmation else { throw RecoveryError.invalidPassword }
            try writeNewFile(try makeEnvelope(masterKey: master, passphrase: password), at: file)
            print("Encrypted recovery kit created. Store it separately from your backups.")
        } else {
            guard try readMasterKey() == nil else { throw RecoveryError.keyAlreadyExists }
            let raw = try readRecoveryFile(file)
            let password = try askSecret("Recovery passphrase: ")
            let master = try openEnvelope(raw, passphrase: password)
            // Keychain is written ONLY after successful authenticated decryption.
            try installMasterKey(master)
            print("Keychain recovery key installed. Now restore your encrypted data backup.")
        }
    }
}

do {
    try run()
} catch {
    FileHandle.standardError.write(Data("JAFAR recovery error: \(error)\n".utf8))
    exit(2)
}
#else
fatalError("macOS Keychain recovery is supported only on macOS")
#endif
