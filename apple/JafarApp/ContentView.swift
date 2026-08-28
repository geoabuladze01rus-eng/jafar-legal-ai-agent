import SwiftUI

struct ContentView: View {
    @EnvironmentObject private var localBackend: LocalBackendManager
    @StateObject private var voice = VoiceSessionViewModel(commandClient: JafarClientConfiguration.makeCommandClient(), userId: "local-user")
    @State private var commandText = ""
    @State private var selected: JafarSection = .home
    @State private var showingSettings = false
    @State private var showingCreateMenu = false

    var body: some View {
        NavigationSplitView {
            JafarSidebar(selection: $selected, backend: localBackend) { showingSettings = true }
        } detail: {
            if selected == .home {
                JafarDashboardView(commandText: $commandText, voice: voice) {
                    let text = commandText.trimmingCharacters(in: .whitespacesAndNewlines)
                    guard !text.isEmpty else { return }
                    Task { await voice.send(text: text) }
                }
            } else if selected == .matters {
                JafarMattersView()
            } else { JafarComingSoonView(title: selected.title) }
        }
        .preferredColorScheme(.dark)
        .onChange(of: localBackend.state) { _, _ in voice.configure(commandClient: JafarClientConfiguration.makeCommandClient()) }
        .sheet(isPresented: $showingSettings) { JafarConnectionSettingsView() }
    }
}

#Preview { ContentView().environmentObject(LocalBackendManager()) }
