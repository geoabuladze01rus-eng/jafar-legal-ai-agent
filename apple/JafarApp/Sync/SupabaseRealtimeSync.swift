import Foundation
import Supabase

@MainActor
final class SupabaseRealtimeSync {
    private let client: SupabaseClient
    private let store: JafarSyncStore
    private var channel: RealtimeChannelV2?

    init(client: SupabaseClient, store: JafarSyncStore) {
        self.client = client
        self.store = store
    }

    func start() async throws {
        let channel = client.realtimeV2.channel("user:sync_metadata") { config in
            config.isPrivate = true
        }
        self.channel = channel

        let changes = await channel.postgresChange(AnyAction.self, schema: "public", table: "sync_metadata")
        await channel.subscribe()

        Task {
            for await change in changes {
                await handle(change)
            }
        }
    }

    private func handle(_ change: AnyAction) async {
        switch change {
        case .insert(let action):
            await acceptRecord(action.record)
        case .update(let action):
            await acceptRecord(action.record)
        case .delete:
            break
        case .select(let action):
            await acceptRecord(action.record)
        }
    }

    private func acceptRecord(_ record: [String: AnyJSON]) async {
        guard let entityType = record["entity_type"]?.stringValue,
              let entityId = record["entity_id"]?.stringValue,
              let version = record["version"]?.intValue else { return }

        _ = await store.shouldApply(SyncEnvelope(
            deviceId: record["device_id"]?.stringValue ?? "remote",
            userId: record["user_id"]?.stringValue ?? "",
            entityType: entityType,
            entityId: entityId,
            version: version,
            operation: "remote",
            payload: Data(),
            updatedAt: Date()
        ))
    }
}
