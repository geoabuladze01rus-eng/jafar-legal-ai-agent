import SwiftUI

struct SyncConflictView: View {
    let conflict: SyncConflict
    let localDescription: String
    let remoteDescription: String
    let onKeepLocal: () -> Void
    let onAcceptRemote: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            Label("Конфликт синхронизации", systemImage: "arrow.triangle.2.circlepath")
                .font(.title2.bold())

            Text("Джафар обнаружил разные изменения одной сущности. Ничего не перезаписано автоматически.")
                .foregroundStyle(.secondary)

            VStack(alignment: .leading, spacing: 8) {
                Text("На этом устройстве")
                    .font(.headline)
                Text(localDescription)
            }
            .padding()
            .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 16))

            VStack(alignment: .leading, spacing: 8) {
                Text("На другом устройстве")
                    .font(.headline)
                Text(remoteDescription)
            }
            .padding()
            .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 16))

            HStack {
                Button("Оставить мою версию", action: onKeepLocal)
                Spacer()
                Button("Принять удалённую", action: onAcceptRemote)
                    .buttonStyle(.borderedProminent)
            }
        }
        .padding()
        .navigationTitle("Конфликт")
    }
}
