import SwiftUI

struct ConnectedRootView: View {
    @StateObject private var dashboard = DashboardStore(
        client: JafarClientFactory.dashboardClient()
    )

    var body: some View {
        VStack(spacing: 0) {
            liveStatusStrip
            ContentView()
        }
        .background(JafarPalette.background)
        .task {
            await dashboard.refresh()
        }
    }

    private var liveStatusStrip: some View {
        HStack(spacing: 10) {
            Circle()
                .fill(connectionColor)
                .frame(width: 8, height: 8)

            Text(connectionTitle)
                .font(.caption.weight(.semibold))
                .foregroundStyle(.white.opacity(0.88))

            if JafarAPIConfiguration.baseURL != nil && dashboard.errorMessage == nil {
                Divider()
                    .frame(height: 14)
                    .overlay(Color.white.opacity(0.12))

                metric("Дел", value: dashboard.snapshot.activeMatters)
                metric("Срочно", value: dashboard.snapshot.overdueDeadlines)
                metric("7 дней", value: dashboard.snapshot.deadlinesNext7Days)
            }

            Spacer(minLength: 0)

            if dashboard.isLoading {
                ProgressView()
                    .controlSize(.small)
            } else {
                Button {
                    Task { await dashboard.refresh() }
                } label: {
                    Image(systemName: "arrow.clockwise")
                        .font(.caption.weight(.semibold))
                }
                .buttonStyle(.plain)
                .foregroundStyle(JafarPalette.secondaryText)
                .accessibilityLabel("Обновить данные Джафара")
            }
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 9)
        .background(JafarPalette.elevated)
        .overlay(alignment: .bottom) {
            Rectangle()
                .fill(Color.white.opacity(0.06))
                .frame(height: 1)
        }
    }

    private var connectionTitle: String {
        if JafarAPIConfiguration.baseURL == nil {
            return "Локальный режим"
        }
        if dashboard.errorMessage != nil {
            return "Backend недоступен"
        }
        return "Backend подключён"
    }

    private var connectionColor: Color {
        if JafarAPIConfiguration.baseURL == nil {
            return JafarPalette.warning
        }
        if dashboard.errorMessage != nil {
            return JafarPalette.danger
        }
        return JafarPalette.success
    }

    private func metric(_ title: String, value: Int) -> some View {
        HStack(spacing: 4) {
            Text(title)
                .foregroundStyle(JafarPalette.secondaryText)
            Text("\(value)")
                .fontWeight(.bold)
                .foregroundStyle(.white)
        }
        .font(.caption2)
    }
}
