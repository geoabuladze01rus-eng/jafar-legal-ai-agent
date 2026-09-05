import Foundation

struct VoiceCommandEnvironment: Sendable {
    let client: any CommandClient
    let userId: String

    static func current(bundle: Bundle = .main, processInfo: ProcessInfo = .processInfo) -> VoiceCommandEnvironment {
        let environment = processInfo.environment
        let endpointString = environment["JAFAR_COMMAND_ENDPOINT"]
            ?? bundle.object(forInfoDictionaryKey: "JAFARCommandEndpoint") as? String
        let userId = environment["JAFAR_USER_ID"]
            ?? bundle.object(forInfoDictionaryKey: "JAFARUserId") as? String
            ?? "apple-user"
        let tokenStore = KeychainTokenStore()

        // Development/bootstrap path only: migrate a supplied token into Keychain.
        // Remote requests always read credentials from Keychain afterwards.
        if let bootstrapToken = environment["JAFAR_COMMAND_TOKEN"], !bootstrapToken.isEmpty {
            _ = tokenStore.save(bootstrapToken)
        }

        guard
            let endpointString,
            let endpoint = URL(string: endpointString),
            endpoint.scheme == "https" || endpoint.host == "127.0.0.1" || endpoint.host == "localhost"
        else {
            return VoiceCommandEnvironment(client: LocalCommandClient(), userId: userId)
        }

        return VoiceCommandEnvironment(
            client: RemoteCommandClient(endpoint: endpoint, tokenStore: tokenStore),
            userId: userId
        )
    }
}
