import SwiftUI

@main
struct JafarApp: App {
    @AppStorage("justice.onboarding_completed") private var onboardingCompleted = false

    var body: some Scene {
        WindowGroup {
            if onboardingCompleted {
                ConnectedRootView()
            } else {
                JusticeOnboardingView()
            }
        }
    }
}
