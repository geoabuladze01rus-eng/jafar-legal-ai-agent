import Foundation
import Speech

@MainActor
final class VoiceCommandViewModel: ObservableObject {
    @Published private(set) var transcript = ""
    @Published private(set) var response = ""
    @Published private(set) var isListening = false

    private let client: CommandClient
    private let userId: String

    init(client: CommandClient, userId: String) {
        self.client = client
        self.userId = userId
    }

    func submit(transcript: String, device: String = "apple") async {
        self.transcript = transcript
        do {
            let result = try await client.send(
                CommandRequest(text: transcript, sourceDevice: device, userId: userId)
            )
            response = result.message
        } catch {
            response = "Не удалось связаться с Джафаром."
        }
    }
}
