import SwiftUI

@main
struct JafarApp: App {
    @StateObject private var localBackend = LocalBackendManager()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(localBackend)
                .task {
                    localBackend.startIfConfigured()
                }
        }
    }
}
