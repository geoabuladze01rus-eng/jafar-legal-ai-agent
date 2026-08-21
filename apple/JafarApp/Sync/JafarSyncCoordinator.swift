import Foundation

struct JafarSyncEvent: Codable, Sendable, Identifiable {
    let id: UUID
    let entityID: String
    let entityType: String
    let operation: String
    let updatedAt: Date
    let deviceID: String
}

@MainActor
protocol JafarSyncTransport: AnyObject {
    func push(_ event: JafarSyncEvent) async throws
    func pull(since: Date?) async throws -> [JafarSyncEvent]
}

@MainActor
final class JafarSyncCoordinator: ObservableObject {
    @Published private(set) var lastSyncAt: Date?
    @Published private(set) var pendingEvents: [JafarSyncEvent] = []

    private let transport: JafarSyncTransport
    private let deviceID: String

    init(transport: JafarSyncTransport, deviceID: String) {
        self.transport = transport
        self.deviceID = deviceID
    }

    func enqueue(entityID: String, entityType: String, operation: String) {
        pendingEvents.append(JafarSyncEvent(
            id: UUID(),
            entityID: entityID,
            entityType: entityType,
            operation: operation,
            updatedAt: Date(),
            deviceID: deviceID
        ))
    }

    func sync() async throws {
        for event in pendingEvents {
            try await transport.push(event)
        }
        pendingEvents.removeAll()
        _ = try await transport.pull(since: lastSyncAt)
        lastSyncAt = Date()
    }
}
