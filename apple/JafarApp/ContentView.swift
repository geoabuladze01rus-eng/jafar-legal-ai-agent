import SwiftUI

struct ContentView: View {
    @StateObject private var viewModel = VoiceCommandViewModel()

    var body: some View {
        NavigationStack {
            VStack(spacing: 28) {
                Spacer()

                Image(systemName: viewModel.isListening ? "waveform.circle.fill" : "scale.3d")
                    .font(.system(size: 72))
                    .symbolEffect(.pulse, isActive: viewModel.isListening)

                Text("Джафар")
                    .font(.largeTitle.bold())

                Text(viewModel.transcript.isEmpty ? "Скажите команду" : viewModel.transcript)
                    .multilineTextAlignment(.center)
                    .foregroundStyle(.secondary)
                    .padding(.horizontal)

                Button {
                    viewModel.toggleListening()
                } label: {
                    Label(
                        viewModel.isListening ? "Остановить" : "Говорить",
                        systemImage: viewModel.isListening ? "stop.fill" : "mic.fill"
                    )
                    .font(.headline)
                    .frame(maxWidth: .infinity)
                    .padding()
                }
                .buttonStyle(.borderedProminent)
                .padding(.horizontal)

                if !viewModel.response.isEmpty {
                    Text(viewModel.response)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .padding()
                        .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 16))
                        .padding(.horizontal)
                }

                Spacer()
            }
            .navigationTitle("Юридический агент")
        }
    }
}
