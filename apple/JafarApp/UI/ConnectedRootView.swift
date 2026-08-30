import SwiftUI

struct ConnectedRootView: View {
    @StateObject private var dashboard = DashboardStore(
        client: JafarClientFactory.dashboardClient()
    )
    @State private var showingConnectionSettings = false
    @State private var showingLiveDashboard = false
    @State private var showingMatterNavigator = false

    var body: some View {
        VStack(spacing: 0) {
            liveStatusStrip
            if let signal = dashboard.snapshot.signals.first {
                urgentSignalStrip(signal)
            }
            JusticeWorkspaceView(dashboard: dashboard)
        }
        .background(JafarPalette.background)
        .task {
            await refreshDashboard()
        }
        .sheet(isPresented: $showingConnectionSettings) {
            JafarConnectionSettingsView {
                dashboard.reconfigure(client: JafarClientFactory.dashboardClient())
                Task { await refreshDashboard() }
            }
        }
        .sheet(isPresented: $showingLiveDashboard) {
            LiveDashboardView(dashboard: dashboard)
        }
        .sheet(isPresented: $showingMatterNavigator) {
            MatterNavigatorView(dashboard: dashboard)
        }
    }

    private var liveStatusStrip: some View {
        HStack(spacing: 10) {
            JusticePresenceView(
                state: dashboard.errorMessage == nil ? .calm : .control,
                compact: true
            )

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
                metric("Одобрить", value: dashboard.snapshot.pendingApprovals)
            }

            Spacer(minLength: 0)

            if dashboard.isLoading {
                ProgressView()
                    .controlSize(.small)
            } else {
                Button {
                    Task { await refreshDashboard() }
                } label: {
                    Image(systemName: "arrow.clockwise")
                        .font(.caption.weight(.semibold))
                }
                .buttonStyle(.plain)
                .foregroundStyle(JafarPalette.secondaryText)
                .accessibilityLabel("Обновить данные JAFAR AI")
            }

            Button {
                showingMatterNavigator = true
            } label: {
                Image(systemName: "briefcase.fill")
                    .font(.caption.weight(.semibold))
            }
            .buttonStyle(.plain)
            .foregroundStyle(JafarPalette.secondaryText)
            .accessibilityLabel("Открыть дела")

            Button {
                showingLiveDashboard = true
            } label: {
                Image(systemName: "rectangle.3.group.fill")
                    .font(.caption.weight(.semibold))
            }
            .buttonStyle(.plain)
            .foregroundStyle(JafarPalette.secondaryText)
            .accessibilityLabel("Открыть рабочую сводку")

            Button {
                showingConnectionSettings = true
            } label: {
                Image(systemName: "gearshape.fill")
                    .font(.caption.weight(.semibold))
            }
            .buttonStyle(.plain)
            .foregroundStyle(JafarPalette.secondaryText)
            .accessibilityLabel("Настройки подключения")
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

    private func urgentSignalStrip(_ signal: DashboardSignal) -> some View {
        HStack(spacing: 10) {
            Image(
                systemName: signal.requiresApproval
                    ? "checkmark.seal.fill"
                    : "bell.badge.fill"
            )
            .foregroundStyle(signalColor(signal.priority))

            VStack(alignment: .leading, spacing: 2) {
                Text(signal.title)
                    .font(.caption.weight(.semibold))
                    .lineLimit(1)
                Text(signal.body)
                    .font(.caption2)
                    .foregroundStyle(JafarPalette.secondaryText)
                    .lineLimit(1)
            }
            Spacer(minLength: 0)
            Text("P\(signal.priority)")
                .font(.caption2.monospacedDigit().weight(.bold))
                .foregroundStyle(signalColor(signal.priority))
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 8)
        .background(JafarPalette.card)
        .overlay(alignment: .bottom) {
            Rectangle()
                .fill(Color.white.opacity(0.05))
                .frame(height: 1)
        }
    }

    private var connectionTitle: String {
        if JafarAPIConfiguration.baseURL == nil {
            return "JAFAR AI · локальный режим"
        }
        if dashboard.errorMessage != nil {
            return "JAFAR AI · backend недоступен"
        }
        return "JAFAR AI · подключено"
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

    private func signalColor(_ priority: Int) -> Color {
        if priority >= 80 { return JafarPalette.danger }
        if priority >= 50 { return JafarPalette.warning }
        return JafarPalette.accent
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

    @MainActor
    private func refreshDashboard() async {
        await dashboard.refresh()
        JafarAlertsStore.shared.replace(
            with: dashboard.snapshot.signals,
            generatedAt: dashboard.snapshot.generatedAt
        )
    }
}
