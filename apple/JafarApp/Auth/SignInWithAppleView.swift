import AuthenticationServices
import SwiftUI

struct SignInWithAppleView: View {
    @StateObject private var coordinator = AppleSignInCoordinator()
    let onSignedIn: (AppleIdentity) -> Void

    var body: some View {
        VStack(spacing: 20) {
            Text("Доступ к Джафару")
                .font(.title2.bold())

            SignInWithAppleButton(.signIn) { request in
                request.requestedScopes = [.fullName, .email]
            } onCompletion: { result in
                switch result {
                case .success(let authorization):
                    coordinator.handle(authorization)
                    if let identity = coordinator.identity {
                        onSignedIn(identity)
                    }
                case .failure(let error):
                    coordinator.errorMessage = error.localizedDescription
                }
            }
            .signInWithAppleButtonStyle(.black)
            .frame(height: 50)

            if let error = coordinator.errorMessage {
                Text(error)
                    .font(.footnote)
                    .foregroundStyle(.secondary)
            }
        }
        .padding()
    }
}
