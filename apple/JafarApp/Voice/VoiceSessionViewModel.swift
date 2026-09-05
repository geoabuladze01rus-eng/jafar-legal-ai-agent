import AVFoundation
import Combine
import Foundation
import SwiftUI

@MainActor
final class VoiceSessionViewModel: ObservableObject {
    @Published private(set) var transcript = ""
    @Published private(set) var response = ""
    @Published private(set) var intent = ""
    @Published private(set) var isListening = false
    @Published private(set) var isSpeaking = false
    @Published private(set) var isSending = false
    @Published private(set) var approvalRequired = false
    @Published private(set) var errorMessage: String?

    private let recognizer = VoiceRecognizer()
    private let synthesizer = AVSpeechSynthesizer()
    private let commandClient: any CommandClient
    private let userId: String
    private var pendingCommand: String?
    private var speechDelegate: SpeechDelegate?

    init(commandClient: any CommandClient, userId: String) {
        self.commandClient = commandClient
        self.userId = userId
    }

    func start() async {
        errorMessage = nil
        guard !isSending else { return }
        guard await recognizer.requestPermissions() else {
            errorMessage = "Нужен доступ к микрофону и распознаванию речи."
            return
        }
        do {
            try recognizer.start()
            isListening = true
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func stopAndSend() async {
        recognizer.stop()
        isListening = false
        transcript = recognizer.transcript
        let command = transcript.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !command.isEmpty else { return }
        await send(command: command, approved: false)
    }

    func sendText(_ command: String) async {
        let normalized = command.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !normalized.isEmpty else { return }
        transcript = normalized
        await send(command: normalized, approved: false)
    }

    func confirmPendingCommand() async {
        guard let pendingCommand else { return }
        await send(command: pendingCommand, approved: true)
    }

    func cancelPendingCommand() {
        pendingCommand = nil
        approvalRequired = false
        response = "Действие отменено."
        speak(response)
    }

    private func send(command: String, approved: Bool) async {
        guard !isSending else { return }
        isSending = true
        errorMessage = nil
        defer { isSending = false }

        do {
            let result = try await commandClient.send(
                request: CommandRequest(
                    text: command,
                    userId: userId,
                    sourceDevice: Self.sourceDevice,
                    approved: approved
                )
            )
            response = result.message
            intent = result.intent
            approvalRequired = result.approvalRequired
            pendingCommand = result.approvalRequired ? command : nil
            speak(response)
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    private func speak(_ text: String) {
        guard !text.isEmpty else { return }
        synthesizer.stopSpeaking(at: .immediate)
        let utterance = AVSpeechUtterance(string: text)
        utterance.voice = AVSpeechSynthesisVoice(language: "ru-RU")
        utterance.rate = 0.5
        isSpeaking = true
        let delegate = SpeechDelegate { [weak self] in self?.isSpeaking = false }
        speechDelegate = delegate
        synthesizer.delegate = delegate
        synthesizer.speak(utterance)
    }

    private static var sourceDevice: String {
        #if os(iOS)
        return "ios"
        #elseif os(macOS)
        return "macos"
        #else
        return "apple"
        #endif
    }
}

private final class SpeechDelegate: NSObject, AVSpeechSynthesizerDelegate {
    private let completion: () -> Void

    init(completion: @escaping () -> Void) {
        self.completion = completion
    }

    func speechSynthesizer(_ synthesizer: AVSpeechSynthesizer, didFinish utterance: AVSpeechUtterance) {
        completion()
    }

    func speechSynthesizer(_ synthesizer: AVSpeechSynthesizer, didCancel utterance: AVSpeechUtterance) {
        completion()
    }
}
