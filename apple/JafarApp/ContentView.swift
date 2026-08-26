import SwiftUI

struct ContentView: View {
    @EnvironmentObject private var localBackend: LocalBackendManager
    @StateObject private var voice = VoiceSessionViewModel(
        commandClient: JafarClientConfiguration.makeCommandClient(),
        userId: "local-user"
    )
    @State private var endpoint = JafarClientConfiguration.endpointString
    @State private var apiKey = ""
    @State private var commandText = "проверка связи"
    @State private var configurationMessage: String?

    var body: some View {
        NavigationStack {
            Form {
#if os(macOS)
                Section("Локальный Джафар") {
                    switch localBackend.state {
                    case .notConfigured:
                        Text("Первый запуск: выберите папку проекта один раз. После этого backend будет запускаться вместе с приложением автоматически.")
                            .font(.footnote)
                        Button("Выбрать папку Jafar и запустить") {
                            localBackend.chooseRepositoryFolderAndStart()
                        }
                    case .starting:
                        HStack {
                            ProgressView()
                            Text("Запускаю локальный backend…")
                        }
                    case let .running(endpoint):
                        Label("Джафар готов", systemImage: "checkmark.circle.fill")
                        Text(endpoint)
                            .font(.caption)
                            .textSelection(.enabled)
                    case let .failed(message):
                        Text(message)
                            .foregroundStyle(.red)
                        Button("Выбрать папку заново") {
                            localBackend.chooseRepositoryFolderAndStart()
                        }
                    case .stopped:
                        Button("Запустить локальный backend") {
                            localBackend.startIfConfigured()
                        }
                    }
                }
#endif

                Section("Джафар") {
                    TextField("Команда", text: $commandText)

                    Button("Отправить команду") {
                        Task {
                            await voice.send(text: commandText)
                        }
                    }
                    .buttonStyle(.borderedProminent)
                    .disabled(commandText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)

                    Button(voice.isListening ? "Остановить и отправить" : "Голосовая команда") {
                        Task {
                            if voice.isListening {
                                await voice.stopAndSend()
                            } else {
                                await voice.start()
                            }
                        }
                    }

                    if !voice.transcript.isEmpty {
                        Text("Команда: \(voice.transcript)")
                            .font(.footnote)
                    }

                    if !voice.response.isEmpty {
                        Text(voice.response)
                    }

                    if let error = voice.errorMessage {
                        Text(error)
                            .foregroundStyle(.red)
                    }
                }

                DisclosureGroup("Дополнительные настройки API") {
                    TextField("http://127.0.0.1:8000/v1/command", text: $endpoint)
#if os(iOS)
                        .textInputAutocapitalization(.never)
                        .keyboardType(.URL)
#endif
                    SecureField("API-ключ", text: $apiKey)

                    Button("Сохранить подключение") {
                        saveConfiguration()
                    }

                    if let configurationMessage {
                        Text(configurationMessage)
                            .font(.footnote)
                    }
                }
            }
            .navigationTitle("Джафар")
        }
        .onChange(of: localBackend.state) { _, newState in
            if case let .running(newEndpoint) = newState {
                endpoint = newEndpoint
                voice.configure(commandClient: JafarClientConfiguration.makeCommandClient())
                configurationMessage = "Локальный backend подключён автоматически."
            }
        }
    }

    private func saveConfiguration() {
        do {
            try JafarClientConfiguration.save(
                endpoint: endpoint,
                apiKey: apiKey.isEmpty ? nil : apiKey
            )
            voice.configure(commandClient: JafarClientConfiguration.makeCommandClient())
            apiKey = ""
            configurationMessage = "Подключение сохранено. API-ключ хранится в Keychain."
        } catch {
            configurationMessage = error.localizedDescription
        }
    }
}

#Preview {
    ContentView()
        .environmentObject(LocalBackendManager())
}
