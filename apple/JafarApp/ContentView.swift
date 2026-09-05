import SwiftUI

struct ContentView: View {
    @StateObject private var voice: VoiceSessionViewModel

    init(environment: VoiceCommandEnvironment = .current()) {
        _voice = StateObject(
            wrappedValue: VoiceSessionViewModel(
                commandClient: environment.client,
                userId: environment.userId
            )
        )
    }

    var body: some View {
        NavigationStack {
            VStack(spacing: 20) {
                Text("Джафар")
                    .font(.largeTitle.bold())

                #if os(macOS)
                LocalAIStatusView()
                #endif

                if !voice.transcript.isEmpty {
                    Text(voice.transcript)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }

                if !voice.response.isEmpty {
                    Text(voice.response)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }

                if voice.approvalRequired {
                    HStack {
                        Button("Отмена") {
                            voice.cancelPendingCommand()
                        }
                        .buttonStyle(.bordered)

                        Button("Подтвердить") {
                            Task { await voice.confirmPendingCommand() }
                        }
                        .buttonStyle(.borderedProminent)
                    }
                } else {
                    Button(voice.isListening ? "Остановить" : "Голосовая команда") {
                        Task {
                            if voice.isListening {
                                await voice.stopAndSend()
                            } else {
                                await voice.start()
                            }
                        }
                    }
                    .buttonStyle(.borderedProminent)
                    .disabled(voice.isSending)
                }

                if voice.isSending {
                    ProgressView("Джафар выполняет команду…")
                }

                if let error = voice.errorMessage {
                    Text(error)
                        .foregroundStyle(.red)
                        .multilineTextAlignment(.center)
                }
            }
            .padding()
            .navigationTitle("Джафар")
        }
    }
}

#Preview {
    ContentView(environment: VoiceCommandEnvironment(client: LocalCommandClient(), userId: "preview-user"))
}
