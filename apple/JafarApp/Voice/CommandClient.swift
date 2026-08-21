import Foundation

struct CommandRequest: Codable, Sendable {
    let text: String
    let userId: String
    let sourceDevice: String
}

struct CommandResponse: Codable, Sendable {
    let message: String
}

protocol CommandClient: Sendable {
    func send(request: CommandRequest) async throws -> CommandResponse
}

struct LocalCommandClient: CommandClient {
    func send(request: CommandRequest) async throws -> CommandResponse {
        CommandResponse(message: "Команда получена: \(request.text)")
    }
}
