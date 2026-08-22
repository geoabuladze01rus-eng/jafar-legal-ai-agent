import AppIntents

struct JafarVoiceIntent: AppIntent {
    static let title: LocalizedStringResource = "Спросить Джафара"
    static let description = IntentDescription("Передаёт голосовую команду юридическому AI-агенту Джафару.")
    static let openAppWhenRun = true

    @Parameter(title: "Команда")
    var command: String

    func perform() async throws -> some IntentResult & ProvidesDialog {
        .result(dialog: "Передаю команду Джафару: \(command)")
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
