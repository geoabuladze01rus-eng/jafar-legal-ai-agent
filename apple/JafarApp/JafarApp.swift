import SwiftUI

#if os(macOS)
import AppKit

final class JusticiaApplicationDelegate: NSObject, NSApplicationDelegate {
    func applicationWillTerminate(_ notification: Notification) {
        BackendRuntime.shared.shutdownForApplicationTermination()
    }
}
#endif

@main
struct JusticiaApp: App {
    #if os(macOS)
    @StateObject private var backend = BackendRuntime.shared
    @NSApplicationDelegateAdaptor(JusticiaApplicationDelegate.self) private var applicationDelegate
    #endif

    var body: some Scene {
        WindowGroup("Юстиция") {
            #if os(macOS)
            ContentView(environment: backend.environment, backend: backend)
                .id(backend.sessionID)
                .task { await backend.start() }
                .onDisappear { backend.stop() }
                .frame(minWidth: 1180, minHeight: 760)
            #else
            ContentView()
            #endif
        }
        #if os(macOS)
        .defaultSize(width: 1440, height: 900)
        #endif
    }
}
