import SwiftUI

struct JafarConflictResolutionView: View {
    let conflict: SyncConflict
    let localSummary: String
    let remoteSummary: String
    let onKeepLocal: () -> Void
    let onAcceptRemote: () -> Void
    let onCancel: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Требуется решение")
                .font(.title2.bold())
            Text("Джафар обнаружил конфликт синхронизации. Юридически значимое изменение не будет перезаписано автоматически.")
                .foregroundStyle(.secondary)

            GroupBox("На этом устройстве") {
                Text(localSummary)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }

            GroupBox("На другом устройстве") {
                Text(remoteSummary)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }

            HStack {
                Button("Оставить мою версию", action: onKeepLocal)
                Button("Принять другую версию", action: onAcceptRemote)
                    .buttonStyle(.borderedProminent)
                Button("Позже", action: onCancel)
            }
        }
        .padding()
        .navigationTitle("Конфликт")
    }
}
