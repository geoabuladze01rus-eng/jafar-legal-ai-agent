import Foundation

#if os(macOS)
import AppKit
#endif

@MainActor
final class LocalBackendManager: ObservableObject {
    enum State: Equatable {
        case notConfigured
        case starting
        case running(endpoint: String)
        case failed(String)
        case stopped
    }

    @Published private(set) var state: State = .notConfigured

    private static let repoRootDefaultsKey = "jafar.local.repo-root"

#if os(macOS)
    private var process: Process?
    private var outputPipe: Pipe?
    private var terminationObserver: NSObjectProtocol?
#endif

    var configuredRepoRoot: String? {
        UserDefaults.standard.string(forKey: Self.repoRootDefaultsKey)
    }

    init() {
#if os(macOS)
        terminationObserver = NotificationCenter.default.addObserver(
            forName: NSApplication.willTerminateNotification,
            object: nil,
            queue: .main
        ) { [weak self] _ in
            Task { @MainActor in
                self?.stop()
            }
        }
#endif
    }

    deinit {
#if os(macOS)
        if let terminationObserver {
            NotificationCenter.default.removeObserver(terminationObserver)
        }
#endif
    }

    func startIfConfigured() {
#if os(macOS)
        guard process == nil else { return }
        guard let root = configuredRepoRoot, !root.isEmpty else {
            state = .notConfigured
            return
        }
        start(repoRoot: root)
#else
        state = .stopped
#endif
    }

#if os(macOS)
    func chooseRepositoryFolderAndStart() {
        let panel = NSOpenPanel()
        panel.title = "Выберите папку jafar-legal-ai-agent"
        panel.message = "Джафар запомнит её и дальше будет запускать локальный backend автоматически."
        panel.canChooseFiles = false
        panel.canChooseDirectories = true
        panel.allowsMultipleSelection = false
        panel.prompt = "Выбрать"

        guard panel.runModal() == .OK, let url = panel.url else { return }
        let path = url.path
        guard Self.isValidRepoRoot(path) else {
            state = .failed("В выбранной папке не найден scripts/private_beta_backend_smoke.py или .venv/bin/python.")
            return
        }

        UserDefaults.standard.set(path, forKey: Self.repoRootDefaultsKey)
        start(repoRoot: path)
    }

    func start(repoRoot: String) {
        guard process == nil else { return }
        guard Self.isValidRepoRoot(repoRoot) else {
            state = .failed("Локальная папка Jafar больше недоступна. Выберите её заново.")
            return
        }

        state = .starting

        let rootURL = URL(fileURLWithPath: repoRoot, isDirectory: true)
        let pythonURL = rootURL.appendingPathComponent(".venv/bin/python")
        let scriptURL = rootURL.appendingPathComponent("scripts/private_beta_backend_smoke.py")

        let task = Process()
        task.executableURL = pythonURL
        task.arguments = ["-u", scriptURL.path, "--hold"]
        task.currentDirectoryURL = rootURL

        let pipe = Pipe()
        task.standardOutput = pipe
        task.standardError = pipe
        outputPipe = pipe

        pipe.fileHandleForReading.readabilityHandler = { [weak self] handle in
            let data = handle.availableData
            guard !data.isEmpty, let text = String(data: data, encoding: .utf8) else { return }
            Task { @MainActor in
                self?.consumeBackendOutput(text)
            }
        }

        task.terminationHandler = { [weak self] finished in
            Task { @MainActor in
                guard let self else { return }
                self.outputPipe?.fileHandleForReading.readabilityHandler = nil
                self.outputPipe = nil
                self.process = nil
                if case .running = self.state {
                    self.state = .stopped
                } else if finished.terminationStatus != 0 {
                    self.state = .failed("Локальный backend завершился с кодом \(finished.terminationStatus).")
                }
                JafarClientConfiguration.clearAPIKey()
            }
        }

        do {
            try task.run()
            process = task
        } catch {
            outputPipe = nil
            process = nil
            state = .failed("Не удалось запустить локальный backend: \(error.localizedDescription)")
        }
    }
#endif

    func stop() {
#if os(macOS)
        outputPipe?.fileHandleForReading.readabilityHandler = nil
        outputPipe = nil
        if let process, process.isRunning {
            process.terminate()
        }
        process = nil
#endif
        JafarClientConfiguration.clearAPIKey()
        if state != .notConfigured {
            state = .stopped
        }
    }

#if os(macOS)
    private func consumeBackendOutput(_ text: String) {
        let lines = text.split(whereSeparator: \ .isNewline).map(String.init)
        var endpoint: String?
        var apiKey: String?

        for line in lines {
            if line.hasPrefix("APPLE_ENDPOINT=") {
                endpoint = String(line.dropFirst("APPLE_ENDPOINT=".count))
            } else if line.hasPrefix("EPHEMERAL_API_KEY=") {
                apiKey = String(line.dropFirst("EPHEMERAL_API_KEY=".count))
            }
        }

        if let endpoint, let apiKey {
            do {
                try JafarClientConfiguration.save(endpoint: endpoint, apiKey: apiKey)
                state = .running(endpoint: endpoint)
            } catch {
                state = .failed("Backend запущен, но не удалось настроить подключение: \(error.localizedDescription)")
            }
        }
    }

    private static func isValidRepoRoot(_ path: String) -> Bool {
        let root = URL(fileURLWithPath: path, isDirectory: true)
        let python = root.appendingPathComponent(".venv/bin/python").path
        let script = root.appendingPathComponent("scripts/private_beta_backend_smoke.py").path
        return FileManager.default.isExecutableFile(atPath: python)
            && FileManager.default.fileExists(atPath: script)
    }
#endif
}
