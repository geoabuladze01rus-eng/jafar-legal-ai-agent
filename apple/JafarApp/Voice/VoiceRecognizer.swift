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
    private var tapInstalled = false

    func requestPermissions() async -> Bool {
        let speech = await withCheckedContinuation { continuation in
            SFSpeechRecognizer.requestAuthorization { status in
                continuation.resume(returning: status == .authorized)
            }
        }

#if os(macOS)
        let microphone = await AVCaptureDevice.requestAccess(for: .audio)
#else
        let microphone = await AVAudioApplication.requestRecordPermission()
#endif

        return speech && microphone
    }

    func start() throws {
        guard !isListening else { return }
        guard let recognizer, recognizer.isAvailable else { throw VoiceError.unavailable }

        transcript = ""
        errorMessage = nil
        task?.cancel()
        task = nil
        request = SFSpeechAudioBufferRecognitionRequest()
        guard let request else { throw VoiceError.unavailable }
        request.shouldReportPartialResults = true

        let input = audioEngine.inputNode
        let format = input.inputFormat(forBus: 0)
        guard format.sampleRate > 0, format.channelCount > 0 else {
            self.request = nil
            throw VoiceError.invalidAudioFormat
        }

        if tapInstalled {
            input.removeTap(onBus: 0)
            tapInstalled = false
        }

        input.installTap(onBus: 0, bufferSize: 1024, format: format) { [weak self] buffer, _ in
            self?.request?.append(buffer)
        }
        tapInstalled = true

        do {
            audioEngine.prepare()
            try audioEngine.start()
        } catch {
            input.removeTap(onBus: 0)
            tapInstalled = false
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

    func stop() {
        if audioEngine.isRunning {
            audioEngine.stop()
        }
        if tapInstalled {
            audioEngine.inputNode.removeTap(onBus: 0)
            tapInstalled = false
        }
        request?.endAudio()
        task?.cancel()
        task = nil
        request = nil
        isListening = false
    }
}

enum VoiceError: Error, LocalizedError {
    case unavailable
    case invalidAudioFormat

    var errorDescription: String? {
        switch self {
        case .unavailable:
            return "Распознавание речи сейчас недоступно."
        case .invalidAudioFormat:
            return "Микрофон недоступен или macOS не предоставила корректный аудиоформат. Проверьте доступ к микрофону в Системных настройках."
        }
    }
}
