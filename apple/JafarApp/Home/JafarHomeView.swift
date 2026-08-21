import SwiftUI

struct JafarHomeView: View {
    let snapshot: DashboardSnapshot
    @ObservedObject var voice: VoiceSessionViewModel

    var body: some View {
        TabView {
            JafarDashboardView(snapshot: snapshot)
                .tabItem { Label("Обзор", systemImage: "rectangle.grid.2x2") }

            VStack(spacing: 24) {
                Spacer()
                Text(voice.transcript.isEmpty ? "Готов к работе" : voice.transcript)
                    .multilineTextAlignment(.center)
                    .padding()

                Button {
                    Task {
                        if voice.isListening {
                            await voice.stopAndSend()
                        } else {
                            await voice.start()
                        }
                    }
                } label: {
                    Image(systemName: voice.isListening ? "stop.fill" : "mic.fill")
                        .font(.system(size: 42))
                        .frame(width: 110, height: 110)
                }
                .buttonStyle(.borderedProminent)

                if !voice.response.isEmpty {
                    Text(voice.response)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .padding()
                        .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 18))
                        .padding(.horizontal)
                }
                Spacer()
            }
            .tabItem { Label("Джафар", systemImage: "waveform") }
        }
    }
}
