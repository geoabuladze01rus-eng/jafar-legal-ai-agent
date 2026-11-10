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
import SQLite3

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
    case archiveKeyMismatch

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
        case .archiveKeyMismatch: return "Recovery key does not authenticate the existing local archive. Keychain was not modified."
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

private func databaseCheckValues(_ file: URL) throws -> (Data, Data) {
    // Open existing encrypted databases in read-only mode. Nothing is migrated.
    let status = try? file.resourceValues(forKeys: [.isRegularFileKey, .isSymbolicLinkKey])
    guard status?.isRegularFile == true, status?.isSymbolicLink != true else {
        throw RecoveryError.archiveKeyMismatch
    }
    var database: OpaquePointer?
    guard sqlite3_open_v2(
        file.path, &database, SQLITE_OPEN_READONLY | SQLITE_OPEN_FULLMUTEX, nil
    ) == SQLITE_OK, let connection = database else {
        if database != nil { sqlite3_close(database) }
        throw RecoveryError.archiveKeyMismatch
    }
    defer { sqlite3_close(connection) }
    var statement: OpaquePointer?
    let query =
        "SELECT " +
        "(SELECT value FROM metadata WHERE key='key_check_nonce'), " +
        "(SELECT value FROM metadata WHERE key='key_check_payload')"
    guard sqlite3_prepare_v2(connection, query, -1, &statement, nil) == SQLITE_OK,
          let prepared = statement else {
        if statement != nil { sqlite3_finalize(statement) }
        throw RecoveryError.archiveKeyMismatch
    }
    defer { sqlite3_finalize(prepared) }
    guard sqlite3_step(prepared) == SQLITE_ROW,
          sqlite3_column_type(prepared, 0) == SQLITE_BLOB,
          sqlite3_column_type(prepared, 1) == SQLITE_BLOB,
          let noncePointer = sqlite3_column_blob(prepared, 0),
          let cipherPointer = sqlite3_column_blob(prepared, 1) else {
        throw RecoveryError.archiveKeyMismatch
    }
    let nonce = Data(
        bytes: noncePointer, count: Int(sqlite3_column_bytes(prepared, 0))
    )
    let ciphertext = Data(
        bytes: cipherPointer, count: Int(sqlite3_column_bytes(prepared, 1))
    )
    guard nonce.count == 12, ciphertext.count > 16 else {
        throw RecoveryError.archiveKeyMismatch
    }
    return (nonce, ciphertext)
}

private func verifyAgainstExistingArchive(_ masterKey: Data) throws {
    // Import on a fresh Mac has no data yet. If a partially restored home
    // exists, authenticate every available core database BEFORE SecItemAdd.
    let home = dataHome()
    let known = [
        ("matters.sqlite3", "jafar-desktop-matter-storage-v1", "jafar-desktop-storage-check-v1"),
        ("corpus.sqlite3", "jafar-desktop-corpus-storage-v1", "jafar-desktop-corpus-check-v1")
    ]
    let manager = FileManager.default
    var authenticated = 0
    for (filename, context, checkValue) in known {
        let path = home.appendingPathComponent(filename)
        guard manager.fileExists(atPath: path.path) else { continue }
        authenticated += 1
        let (nonce, payload) = try databaseCheckValues(path)
        let key = HKDF<SHA256>.deriveKey(
            inputKeyMaterial: SymmetricKey(data: masterKey),
            salt: Data("JAFAR desktop storage".utf8),
            info: Data(context.utf8),
            outputByteCount: 32
        )
        do {
            let box = try AES.GCM.SealedBox(
                nonce: AES.GCM.Nonce(data: nonce),
                ciphertext: Data(payload.dropLast(16)),
                tag: Data(payload.suffix(16))
            )
            let plain = try AES.GCM.open(
                box, using: key, authenticating: Data("metadata:check".utf8)
            )
            guard plain == Data(checkValue.utf8) else {
                throw RecoveryError.archiveKeyMismatch
            }
        } catch {
            throw RecoveryError.archiveKeyMismatch
        }
    }
    if authenticated == 0 {
        let extra = [
            "drafts.sqlite3",
            "claim-review-decisions.sqlite3"
        ]
        let otherDatabases = extra.contains {
            manager.fileExists(atPath: home.appendingPathComponent($0).path)
        }
        let documents = home.appendingPathComponent("documents", isDirectory: true)
        let anyBlobs = (
            try? manager.contentsOfDirectory(
                at: documents, includingPropertiesForKeys: nil
            )
        )?.contains(where: { $0.pathExtension == "jafarblob" }) ?? false
        if otherDatabases || anyBlobs {
            throw RecoveryError.archiveKeyMismatch
        }
    }
}

private func installMasterKey(_ data: Data) throws {
    guard data.count == 32 else { throw RecoveryError.invalidFile }
    guard try readMasterKey() == nil else { throw RecoveryError.keyAlreadyExists }
    try verifyAgainstExistingArchive(data)
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
    // Test the existing-database key identity preflight without touching
    // any real JAFAR data or the Keychain.
    let testHome = FileManager.default.temporaryDirectory
        .appendingPathComponent("jafar-key-recovery-self-test-" + UUID().uuidString)
    try FileManager.default.createDirectory(
        at: testHome, withIntermediateDirectories: false
    )
    defer { try? FileManager.default.removeItem(at: testHome) }
    let oldHome = ProcessInfo.processInfo.environment["JAFAR_DESKTOP_HOME"]
    setenv("JAFAR_DESKTOP_HOME", testHome.path, 1)
    defer {
        if let oldHome {
            setenv("JAFAR_DESKTOP_HOME", oldHome, 1)
        } else {
            unsetenv("JAFAR_DESKTOP_HOME")
        }
    }

    let matterKey = HKDF<SHA256>.deriveKey(
        inputKeyMaterial: SymmetricKey(data: key),
        salt: Data("JAFAR desktop storage".utf8),
        info: Data("jafar-desktop-matter-storage-v1".utf8),
        outputByteCount: 32
    )
    let check = try AES.GCM.seal(
        Data("jafar-desktop-storage-check-v1".utf8),
        using: matterKey, authenticating: Data("metadata:check".utf8)
    )
    let nonce = Data(check.nonce)
    let cipher = check.ciphertext + check.tag
    func hex(_ data: Data) -> String {
        data.map { String(format: "%02x", $0) }.joined()
    }
    let databasePath = testHome.appendingPathComponent("matters.sqlite3").path
    var conn: OpaquePointer?
    guard sqlite3_open(databasePath, &conn) == SQLITE_OK, let db = conn else {
        if conn != nil { sqlite3_close(conn) }
        throw RecoveryError.cryptography
    }
    let sql =
        "CREATE TABLE metadata (key TEXT PRIMARY KEY, value BLOB NOT NULL);" +
        "INSERT INTO metadata VALUES ('key_check_nonce', X'\(hex(nonce))');" +
        "INSERT INTO metadata VALUES ('key_check_payload', X'\(hex(cipher))');"
    guard sqlite3_exec(db, sql, nil, nil, nil) == SQLITE_OK else {
        sqlite3_close(db)
        throw RecoveryError.cryptography
    }
    sqlite3_close(db)
    try verifyAgainstExistingArchive(key)
    var wrongKeyRejected = false
    do {
        try verifyAgainstExistingArchive(try randomBytes(32))
    } catch RecoveryError.archiveKeyMismatch {
        wrongKeyRejected = true
    }
    guard wrongKeyRejected else { throw RecoveryError.cryptography }

    print("Recovery codec and archive key preflight self-tests passed; Keychain was not accessed.")
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
    // Enforce terminal-only use BEFORE reading any Keychain item.
    guard isatty(STDIN_FILENO) == 1 else { throw RecoveryError.needsTerminal }
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
