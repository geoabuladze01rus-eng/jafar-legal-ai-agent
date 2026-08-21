import Foundation

struct AppConfiguration: Sendable {
    let gatewayBaseURL: URL

    static func load() -> AppConfiguration {
        let raw = ProcessInfo.processInfo.environment["JAFAR_GATEWAY_URL"] ?? "http://localhost:8000"
        guard let url = URL(string: raw) else {
            preconditionFailure("Invalid JAFAR_GATEWAY_URL")
        }
        return AppConfiguration(gatewayBaseURL: url)
    }
}
