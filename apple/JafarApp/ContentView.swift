import SwiftUI

struct ContentView: View {
    @StateObject private var voice = VoiceSessionViewModel(
        commandClient: LocalCommandClient(),
        userId: "local-user"
    )

    var body: some View {
        NavigationStack {
            VStack(spacing: 20) {
                Text("Джафар")
                    .font(.largeTitle.bold())

                if !voice.transcript.isEmpty {
                    Text(voice.transcript)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }

                if !voice.response.isEmpty {
                    Text(voice.response)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }

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
    ContentView()
}
