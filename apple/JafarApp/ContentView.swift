import SwiftUI

struct ContentView: View {
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

                Section("Подключение к API") {
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
}
