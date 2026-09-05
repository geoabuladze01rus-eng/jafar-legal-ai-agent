#if os(macOS)
import Darwin
import Foundation
import Security

@MainActor
final class BackendRuntime: ObservableObject {
    static let shared = BackendRuntime()
    enum State: Equatable {
        case stopped
        case starting
        case ready
        case failed(String)
        case stopping
    }

    @Published private(set) var state: State = .stopped
    @Published private(set) var sessionID = UUID()
    private let supervisor: BackendSupervisor

    init(supervisor: BackendSupervisor = BackendSupervisor()) {
        self.supervisor = supervisor
        supervisor.onUnexpectedTermination = { [weak self] in
            Task { @MainActor in
                self?.sidecarDidTerminate()
            }
        }
    }

    var environment: VoiceCommandEnvironment {
        guard case .ready = state, let endpoint = supervisor.commandEndpoint,
              let token = supervisor.ipcToken else {
            return VoiceCommandEnvironment(client: LocalCommandClient(), userId: "apple-user")
        }
        return VoiceCommandEnvironment(
            client: RemoteCommandClient(endpoint: endpoint, token: token),
            userId: "apple-user"
        )
    }

    func start() async {
        guard state == .stopped || isFailed else { return }
        state = .starting
        do {
            try await supervisor.start()
            state = .ready
            sessionID = UUID()
        } catch {
            state = .failed("Не удалось запустить локальный движок JAFAR.")
        }
    }

    func stop() {
        guard state != .stopped else { return }
        state = .stopping
        supervisor.stop()
        state = .stopped
    }

    func shutdownForApplicationTermination() {
        supervisor.stop()
    }

    private func sidecarDidTerminate() {
        guard state != .stopping && state != .stopped else { return }
        state = .failed("Локальный движок JAFAR завершился. Повторите запуск.")
    }

    var isFailed: Bool {
        if case .failed = state { return true }
        return false
    }

    var title: String {
        switch state {
        case .stopped, .stopping: "LOCAL ENGINE STOPPED"
        case .starting: "STARTING JAFAR"
        case .ready: "LOCAL ENGINE READY"
        case .failed: "LOCAL ENGINE FAILED"
        }
    }

    var storageTitle: String {
        switch state {
        case .ready: "LOCAL STORAGE READY"
        case .starting: "INITIALIZING LOCAL STORAGE"
        case .failed: "LOCAL STORAGE UNAVAILABLE"
        case .stopped, .stopping: "LOCAL STORAGE STOPPED"
        }
    }
}

final class BackendSupervisor {
    private(set) var commandEndpoint: URL?
    private(set) var ipcToken: String?
    private var process: Process?
    var onUnexpectedTermination: (() -> Void)?
    private var stopping = false
    private let session = URLSession(configuration: .ephemeral)
    private let startupTimeout: TimeInterval = 18

    func start() async throws {
        stop()
        stopping = false
        guard let executable = Bundle.main.resourceURL?
            .appendingPathComponent("Helpers/JafarBackend/JafarBackend"),
            FileManager.default.isExecutableFile(atPath: executable.path) else {
            throw BackendSupervisorError.missingSidecar
        }

        let port = try loopbackPort()
        let token = randomToken()
        let storageKey = try DesktopStorageKey().loadOrCreate()
        let task = Process()
        task.executableURL = executable
        task.arguments = ["--host", "127.0.0.1", "--port", String(port)]
        task.environment = safeEnvironment(token: token, storageKey: storageKey)
        task.standardOutput = FileHandle.nullDevice
        task.standardError = FileHandle.nullDevice
        task.terminationHandler = { [weak self] _ in
            let unexpected = self?.stopping == false
            self?.commandEndpoint = nil
            self?.ipcToken = nil
            if unexpected {
                self?.onUnexpectedTermination?()
            }
        }
        try task.run()
        process = task
        ipcToken = token
        commandEndpoint = URL(string: "http://127.0.0.1:\(port)/v1/command")

        let deadline = Date().addingTimeInterval(startupTimeout)
        while Date() < deadline {
            if !task.isRunning { throw BackendSupervisorError.exitedBeforeReady }
            if await healthIsReady(port: port) { return }
            try await Task.sleep(nanoseconds: 250_000_000)
        }
        stop()
        throw BackendSupervisorError.timeout
    }

    func stop() {
        stopping = true
        guard let process else { return }
        if process.isRunning {
            process.terminate()
        }
        self.process = nil
        commandEndpoint = nil
        ipcToken = nil
    }

    private func healthIsReady(port: Int) async -> Bool {
        guard let url = URL(string: "http://127.0.0.1:\(port)/health") else { return false }
        do {
            let (_, response) = try await session.data(from: url)
            return (response as? HTTPURLResponse)?.statusCode == 200
        } catch {
            return false
        }
    }

    private func randomToken() -> String {
        var bytes = [UInt8](repeating: 0, count: 32)
        _ = SecRandomCopyBytes(kSecRandomDefault, bytes.count, &bytes)
        return Data(bytes).base64EncodedString(options: [.endLineWithLineFeed])
            .replacingOccurrences(of: "+", with: "-")
            .replacingOccurrences(of: "/", with: "_")
            .replacingOccurrences(of: "=", with: "")
            .replacingOccurrences(of: "\n", with: "")
    }

    private func safeEnvironment(token: String, storageKey: String) -> [String: String] {
        [
            "HOME": NSHomeDirectory(),
            "LANG": "ru_RU.UTF-8",
            "JAFAR_RUNTIME_MODE": "desktop",
            "JAFAR_DESKTOP_IPC_TOKEN": token,
            // Child-only environment transport: no shell or command-line exposure.
            "JAFAR_DESKTOP_STORAGE_KEY": storageKey,
            "JAFAR_DESKTOP_PARENT_PID": String(getpid()),
            "JAFAR_PRODUCTION_SEND": "false",
            "JAFAR_TELEGRAM_POLLING_ENABLED": "false",
            "JAFAR_CONFIDENTIAL_CLOUD_FALLBACK": "false",
        ]
    }

    private func loopbackPort() throws -> Int {
        // The backend accepts only 127.0.0.1.  The short bind-close window is handled
        // by controlled startup retries at the user interaction level, never by a
        // fixed globally shared development port.
        let socketFD = socket(AF_INET, SOCK_STREAM, 0)
        guard socketFD >= 0 else { throw BackendSupervisorError.portUnavailable }
        defer { close(socketFD) }
        var address = sockaddr_in()
        address.sin_len = UInt8(MemoryLayout<sockaddr_in>.size)
        address.sin_family = sa_family_t(AF_INET)
        address.sin_addr = in_addr(s_addr: inet_addr("127.0.0.1"))
        address.sin_port = 0
        let bindResult = withUnsafePointer(to: &address) {
            $0.withMemoryRebound(to: sockaddr.self, capacity: 1) { bind(socketFD, $0, socklen_t(MemoryLayout<sockaddr_in>.size)) }
        }
        guard bindResult == 0 else { throw BackendSupervisorError.portUnavailable }
        var resolved = sockaddr_in()
        var length = socklen_t(MemoryLayout<sockaddr_in>.size)
        guard withUnsafeMutablePointer(to: &resolved, {
            $0.withMemoryRebound(to: sockaddr.self, capacity: 1) { getsockname(socketFD, $0, &length) }
        }) == 0 else { throw BackendSupervisorError.portUnavailable }
        return Int(UInt16(bigEndian: resolved.sin_port))
    }
}

enum BackendSupervisorError: Error {
    case missingSidecar
    case exitedBeforeReady
    case timeout
    case portUnavailable
}
#endif
