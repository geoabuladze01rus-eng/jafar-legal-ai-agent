import SwiftUI

struct JafarSidebar: View {
    @Binding var selection: JafarSection
    let backend: LocalBackendManager
    let openSettings: () -> Void
    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("JAFAR AI").font(.title3.weight(.bold)).foregroundStyle(JafarPalette.gold)
            Text("Юридический помощник адвоката").font(.caption).foregroundStyle(JafarPalette.secondary).padding(.bottom, 16)
            ForEach(JafarSection.allCases) { section in
                Button { if section == .settings { openSettings() } else { selection = section } } label: { Label(section.title, systemImage: section.icon).frame(maxWidth: .infinity, alignment: .leading) }.buttonStyle(.plain).padding(.vertical, 7).padding(.horizontal, 9).background(selection == section ? JafarPalette.mutedGold.opacity(0.28) : .clear, in: RoundedRectangle(cornerRadius: 8)).foregroundStyle(selection == section ? JafarPalette.gold : JafarPalette.text).accessibilityLabel(section.title)
            }
            Spacer(); Label(status, systemImage: running ? "checkmark.circle.fill" : "exclamationmark.triangle").font(.caption).foregroundStyle(running ? .green : .orange)
        }.padding(18).frame(minWidth: 220).background(JafarPalette.background)
    }
    private var running: Bool { if case .running = backend.state { return true }; return false }
    private var status: String { if running { return "Джафар готов" }; if case .starting = backend.state { return "Backend запускается" }; return "Backend недоступен" }
}
