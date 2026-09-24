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
        #if os(macOS)
        JusticiaRootView(
            voice: voice,
            backendStatusText: backend?.title,
            backendFailed: backend?.isFailed ?? false,
            retryBackend: {
                guard let backend else { return }
                Task { await backend.start() }
            }
        )
        #else
        JusticiaRootView(voice: voice)
        #endif
    }
}

#Preview {
    ContentView(environment: VoiceCommandEnvironment(client: LocalCommandClient(), userId: "preview-user"))
}
