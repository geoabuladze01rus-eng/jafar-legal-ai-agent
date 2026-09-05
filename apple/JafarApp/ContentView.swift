import SwiftUI

struct ContentView: View {
    @StateObject private var voice: VoiceSessionViewModel
    #if os(macOS)
    private let backend: BackendRuntime?
    #endif

    #if os(macOS)
    init(environment: VoiceCommandEnvironment = .current(), backend: BackendRuntime? = nil) {
        _voice = StateObject(
            wrappedValue: VoiceSessionViewModel(
                commandClient: environment.client,
                userId: environment.userId
            )
        )
        self.backend = backend
    }
    #else
    init(environment: VoiceCommandEnvironment = .current()) {
        _voice = StateObject(
            wrappedValue: VoiceSessionViewModel(
                commandClient: environment.client,
                userId: environment.userId
            )
        )
    }
    #endif

    var body: some View {
        NavigationStack {
            VStack(spacing: 20) {
                Text("Джафар")
                    .font(.largeTitle.bold())

                #if os(macOS)
                if let backend {
                    Text(backend.title)
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(backend.isFailed ? .red : .secondary)
                    Text(backend.storageTitle)
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(backend.isFailed ? .red : .secondary)
                    if backend.isFailed {
                        Button("Повторить") { Task { await backend.start() } }
                            .buttonStyle(.bordered)
                    }
                }
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
