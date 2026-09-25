import AppIntents

struct JusticiaVoiceIntent: AppIntent {
    static let title: LocalizedStringResource = "Спросить «Юстицию»"
    static let description = IntentDescription("Передаёт голосовую команду юридическому ИИ-помощнику «Юстиция».")
    static let openAppWhenRun = true

    @Parameter(title: "Команда")
    var command: String

    func perform() async throws -> some IntentResult & ProvidesDialog {
        let environment = VoiceCommandEnvironment.current()
        let response = try await environment.client.send(
            request: CommandRequest(
                text: command,
                userId: environment.userId,
                sourceDevice: "app_intent",
                approved: false
            )
        )
        if response.approvalRequired {
            return .result(dialog: "\(response.message) Откройте «Юстицию» и подтвердите действие.")
        }
        return .result(dialog: "\(response.message)")
    }
}

struct JusticiaAppShortcuts: AppShortcutsProvider {
    static var appShortcuts: [AppShortcut] {
        AppShortcut(
            intent: JusticiaVoiceIntent(),
            phrases: [
                "Спроси \(.applicationName)",
                "Спросить \(.applicationName)",
                "Команда \(.applicationName)"
            ],
            shortTitle: "Юстиция",
            systemImageName: "waveform"
        )
    }
}
