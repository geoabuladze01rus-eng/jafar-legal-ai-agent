import AVFoundation
import Combine
import Foundation
import Speech

@MainActor
final class VoiceRecognizer: ObservableObject {
    @Published private(set) var transcript = ""
    @Published private(set) var isListening = false
    @Published private(set) var errorMessage: String?

    private let recognizer = SFSpeechRecognizer(locale: Locale(identifier: "ru-RU"))
    private let audioEngine = AVAudioEngine()
    private var request: SFSpeechAudioBufferRecognitionRequest?
    private var task: SFSpeechRecognitionTask?

    func requestPermissions() async -> Bool {
        let speech = await withCheckedContinuation { continuation in
            SFSpeechRecognizer.requestAuthorization { status in
                continuation.resume(returning: status == .authorized)
            }
        }
        let microphone = await AVAudioApplication.requestRecordPermission()
        return speech && microphone
    }

    func start() throws {
        guard !isListening else { return }
        guard let recognizer, recognizer.isAvailable else { throw VoiceError.unavailable }
        guard recognizer.supportsOnDeviceRecognition else {
            throw VoiceError.onDeviceRecognitionUnavailable
        }

        transcript = ""
        errorMessage = nil
        task?.cancel()

        request = SFSpeechAudioBufferRecognitionRequest()
        guard let request else { throw VoiceError.unavailable }
        request.shouldReportPartialResults = true
        request.requiresOnDeviceRecognition = true

        let input = audioEngine.inputNode
        let format = input.outputFormat(forBus: 0)
        input.removeTap(onBus: 0)
        input.installTap(onBus: 0, bufferSize: 1024, format: format) { [weak self] buffer, _ in
            self?.request?.append(buffer)
        }

        audioEngine.prepare()
        do {
            try audioEngine.start()
        } catch {
            input.removeTap(onBus: 0)
            self.request = nil
            throw error
        }

        isListening = true
        task = recognizer.recognitionTask(with: request) { [weak self] result, error in
            Task { @MainActor in
                if let result {
                    self?.transcript = result.bestTranscription.formattedString
                }
                if error != nil {
                    self?.stop()
                }
            }
        }
    }

    func transcribeFileOnDevice(url: URL) async throws -> String {
        let authorized = await withCheckedContinuation { continuation in
            SFSpeechRecognizer.requestAuthorization { status in
                continuation.resume(returning: status == .authorized)
            }
        }
        guard authorized else { throw VoiceError.permissionDenied }
        guard let recognizer, recognizer.isAvailable else { throw VoiceError.unavailable }
        guard recognizer.supportsOnDeviceRecognition else {
            throw VoiceError.onDeviceRecognitionUnavailable
        }

        let recognitionRequest = SFSpeechURLRecognitionRequest(url: url)
        recognitionRequest.shouldReportPartialResults = false
        recognitionRequest.requiresOnDeviceRecognition = true

        return try await withCheckedThrowingContinuation { continuation in
            var finished = false
            let recognitionTask = recognizer.recognitionTask(with: recognitionRequest) { result, error in
                guard !finished else { return }
                if let error {
                    finished = true
                    continuation.resume(throwing: error)
                    return
                }
                if let result, result.isFinal {
                    finished = true
                    continuation.resume(returning: result.bestTranscription.formattedString)
                }
            }
            self.task = recognitionTask
        }
    }

    func stop() {
        audioEngine.stop()
        audioEngine.inputNode.removeTap(onBus: 0)
        request?.endAudio()
        task?.cancel()
        task = nil
        request = nil
        isListening = false
    }
}

enum VoiceError: LocalizedError {
    case unavailable
    case permissionDenied
    case onDeviceRecognitionUnavailable

    var errorDescription: String? {
        switch self {
        case .unavailable:
            "Распознавание речи сейчас недоступно."
        case .permissionDenied:
            "Нужен доступ к распознаванию речи."
        case .onDeviceRecognitionUnavailable:
            "На этом устройстве недоступно локальное on-device распознавание речи. Данные не будут отправлены на серверное распознавание."
        }
    }
}
