import AppIntents

struct JafarVoiceIntent: AppIntent {
    static let title: LocalizedStringResource = "Спросить Джафара"
    static let description = IntentDescription("Передаёт голосовую команду юридическому AI-агенту Джафару.")
    static let openAppWhenRun = true

    @Parameter(title: "Команда")
    var command: String

    func perform() async throws -> some IntentResult & ProvidesDialog {
        guard let client = JafarClientConfiguration.configuredRemoteClient() else {
            return .result(
                dialog: "Сначала откройте Джафар и настройте адрес API и API-ключ."
            )
        }

        do {
            let response = try await client.send(
                request: CommandRequest(
                    text: command,
                    userId: "app-intent-user",
                    sourceDevice: "apple-intent"
                )
            )
            return .result(dialog: "\(response.message)")
        } catch {
            return .result(dialog: "Джафар не смог выполнить команду: \(error.localizedDescription)")
        }
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
