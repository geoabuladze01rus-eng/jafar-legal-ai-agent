import SwiftUI

#if os(macOS)
import AppKit

final class JafarApplicationDelegate: NSObject, NSApplicationDelegate {
    func applicationWillTerminate(_ notification: Notification) {
        BackendRuntime.shared.shutdownForApplicationTermination()
    }
}
#endif

@main
struct JafarApp: App {
    #if os(macOS)
    @StateObject private var backend = BackendRuntime.shared
    @NSApplicationDelegateAdaptor(JafarApplicationDelegate.self) private var applicationDelegate
    #endif

    var body: some Scene {
        WindowGroup {
            #if os(macOS)
            ContentView(environment: backend.environment, backend: backend)
                .id(backend.sessionID)
                .task { await backend.start() }
                .onDisappear { backend.stop() }
            #else
            ContentView()
            #endif
        }
    }
}
