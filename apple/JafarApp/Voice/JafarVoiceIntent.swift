import AppIntents

struct JafarVoiceIntent: AppIntent {
    static let title: LocalizedStringResource = "Спросить Джафара"
    static let description = IntentDescription("Передаёт голосовую команду юридическому AI-агенту Джафару.")
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
            return .result(dialog: "\(response.message) Откройте Джафара и подтвердите действие.")
        }
        return .result(dialog: "\(response.message)")
    }
}

struct JafarAppShortcuts: AppShortcutsProvider {
    static var appShortcuts: [AppShortcut] {
        AppShortcut(
            intent: JafarVoiceIntent(),
            phrases: [
                "Спроси Джафара",
                "Спросить Джафара",
                "Команда Джафару"
            ],
            shortTitle: "Джафар",
            systemImageName: "waveform"
        )
    }
}
