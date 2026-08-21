import AuthenticationServices
import Foundation

struct AppleIdentity: Codable, Sendable {
    let userIdentifier: String
    let email: String?
    let fullName: String?
}

@MainActor
final class AppleSignInCoordinator: NSObject, ObservableObject {
    @Published private(set) var identity: AppleIdentity?
    @Published private(set) var errorMessage: String?

    func handle(_ authorization: ASAuthorization) {
        guard let credential = authorization.credential as? ASAuthorizationAppleIDCredential else {
            errorMessage = "Не удалось получить Apple ID credential."
            return
        }

        let fullName = [credential.fullName?.givenName, credential.fullName?.familyName]
            .compactMap { $0 }
            .joined(separator: " ")

        identity = AppleIdentity(
            userIdentifier: credential.user,
            email: credential.email,
            fullName: fullName.isEmpty ? nil : fullName
        )
        errorMessage = nil
    }
}
