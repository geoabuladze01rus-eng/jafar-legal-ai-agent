import Foundation
import Supabase

struct JafarSyncEvent: Codable, Sendable, Equatable {
    let id: UUID
    let entity: String
    let operation: String
    let entityID: String
    let deviceID: String
    let occurredAt: Date
}

@MainActor
final class JafarRealtimeSync {
    private let supabase: SupabaseClient
    private let deviceID: String
    private var channel: RealtimeChannelV2?
    private var subscriptions = Set<RealtimeSubscription>()

    init(supabase: SupabaseClient, deviceID: String) {
        self.supabase = supabase
        self.deviceID = deviceID
    }

    func start(onEvent: @escaping @Sendable (JafarSyncEvent) async -> Void) async {
        let channel = supabase.realtimeV2.channel("jafar:user:sync") { config in
            config.isPrivate = true
        }
        self.channel = channel

        channel.onBroadcast(event: "sync") { message in
            guard let data = message.payload.data(using: .utf8),
                  let event = try? JSONDecoder().decode(JafarSyncEvent.self, from: data),
                  event.deviceID != self.deviceID else { return }
            Task { await onEvent(event) }
        }
        .store(in: &subscriptions)

        await channel.subscribe()
    }

    func publish(_ event: JafarSyncEvent) async throws {
        guard let channel else { return }
        let data = try JSONEncoder().encode(event)
        let payload = String(data: data, encoding: .utf8) ?? "{}"
        try await channel.broadcast(event: "sync", message: ["payload": payload])
    }

    func stop() async {
        if let channel { await channel.unsubscribe() }
        subscriptions.removeAll()
        channel = nil
    }
}
