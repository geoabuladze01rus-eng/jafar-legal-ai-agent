import AVFoundation
import Foundation
import SwiftUI

@MainActor
final class VoiceSessionViewModel: ObservableObject {
    @Published private(set) var transcript = ""
    @Published private(set) var response = ""
    @Published private(set) var isListening = false
    @Published private(set) var isSpeaking = false
    @Published private(set) var errorMessage: String?

    private let recognizer = VoiceRecognizer()
    private let synthesizer = AVSpeechSynthesizer()
    private let commandClient: CommandClient
    private let userId: String

    init(commandClient: CommandClient, userId: String) {
        self.commandClient = commandClient
        self.userId = userId
    }

    func start() async {
        errorMessage = nil
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
        guard !transcript.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { return }

        do {
            let result = try await commandClient.send(
                text: transcript,
                userId: userId,
                sourceDevice: "apple"
            )
            response = result.message
            speak(response)
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    private func speak(_ text: String) {
        synthesizer.stopSpeaking(at: .immediate)
        let utterance = AVSpeechUtterance(string: text)
        utterance.voice = AVSpeechSynthesisVoice(language: "ru-RU")
        utterance.rate = 0.5
        isSpeaking = true
        synthesizer.delegate = SpeechDelegate { [weak self] in
            self?.isSpeaking = false
        }
        synthesizer.speak(utterance)
    }
}

private final class SpeechDelegate: NSObject, AVSpeechSynthesizerDelegate {
    private let completion: () -> Void
    init(completion: @escaping () -> Void) { self.completion = completion }
    func speechSynthesizer(_ synthesizer: AVSpeechSynthesizer, didFinish utterance: AVSpeechUtterance) {
        completion()
    }
}
