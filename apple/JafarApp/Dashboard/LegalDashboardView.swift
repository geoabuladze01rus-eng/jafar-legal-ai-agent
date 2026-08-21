import SwiftUI

struct LegalDashboardView: View {
    let snapshot: LegalDashboardSnapshot

    var body: some View {
        List(snapshot.items) { item in
            HStack(alignment: .top, spacing: 12) {
                Image(systemName: icon(for: item.kind))
                    .font(.title3)
                VStack(alignment: .leading, spacing: 4) {
                    Text(item.title).font(.headline)
                    Text(item.subtitle)
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                    if let dueAt = item.dueAt {
                        Text(dueAt, style: .date)
                            .font(.caption)
                    }
                    if item.requiresApproval {
                        Text("Требует подтверждения")
                            .font(.caption.bold())
                    }
                }
            }
            .padding(.vertical, 4)
        }
        .navigationTitle("Джафар — Dashboard")
    }

    private func icon(for kind: LegalDashboardItem.Kind) -> String {
        switch kind {
        case .task: return "checklist"
        case .deadline: return "calendar.badge.exclamationmark"
        case .risk: return "exclamationmark.triangle"
        }
    }
}
