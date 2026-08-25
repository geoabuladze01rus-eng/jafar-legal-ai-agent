import SwiftUI

struct ContentView: View {
    @StateObject private var voice = VoiceSessionViewModel(
        commandClient: JafarClientConfiguration.makeCommandClient(),
        userId: "local-user"
    )
    @State private var endpoint = JafarClientConfiguration.endpointString
    @State private var apiKey = ""
    @State private var configurationMessage: String?

    var body: some View {
        NavigationStack {
            Form {
                Section("Джафар") {
                    if !voice.transcript.isEmpty {
                        Text(voice.transcript)
                    }

                    if !voice.response.isEmpty {
                        Text(voice.response)
                    }

                    Button(voice.isListening ? "Остановить и отправить" : "Голосовая команда") {
                        Task {
                            if voice.isListening {
                                await voice.stopAndSend()
                            } else {
                                await voice.start()
                            }
                        }
                    }
                    .buttonStyle(.borderedProminent)

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
