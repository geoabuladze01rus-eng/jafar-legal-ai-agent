import SwiftUI

struct LiveDashboardView: View {
    @Environment(\.dismiss) private var dismiss
    @ObservedObject var dashboard: DashboardStore

    var body: some View {
        NavigationStack {
            ZStack {
                JafarPalette.background
                    .ignoresSafeArea()

                ScrollView {
                    VStack(alignment: .leading, spacing: 18) {
                        metrics
                        urgentSignals
                        matters

                        if let error = dashboard.errorMessage {
                            Label(error, systemImage: "exclamationmark.triangle.fill")
                                .font(.footnote)
                                .foregroundStyle(JafarPalette.danger)
                                .jafarCard()
                        }
                    }
                    .frame(maxWidth: 820)
                    .padding(18)
                    .frame(maxWidth: .infinity)
                }
                .refreshable {
                    await dashboard.refresh()
                }
            }
            .navigationTitle("Рабочая сводка")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Закрыть") {
                        dismiss()
                    }
                }
                ToolbarItem(placement: .primaryAction) {
                    Button {
                        Task { await dashboard.refresh() }
                    } label: {
                        Image(systemName: "arrow.clockwise")
                    }
                    .disabled(dashboard.isLoading)
                    .accessibilityLabel("Обновить рабочую сводку")
                }
            }
        }
        .preferredColorScheme(.dark)
    }

    private var metrics: some View {
        LazyVGrid(
            columns: [GridItem(.adaptive(minimum: 135), spacing: 10)],
            spacing: 10
        ) {
            metricCard(
                "Активные дела",
                value: dashboard.snapshot.activeMatters,
                icon: "briefcase.fill",
                color: JafarPalette.accent
            )
            metricCard(
                "Просрочено",
                value: dashboard.snapshot.overdueDeadlines,
                icon: "exclamationmark.triangle.fill",
                color: dashboard.snapshot.overdueDeadlines > 0
                    ? JafarPalette.danger
                    : JafarPalette.success
            )
            metricCard(
                "Следующие 7 дней",
                value: dashboard.snapshot.deadlinesNext7Days,
                icon: "calendar.badge.clock",
                color: JafarPalette.warning
            )
            metricCard(
                "На одобрение",
                value: dashboard.snapshot.pendingApprovals,
                icon: "checkmark.seal.fill",
                color: JafarPalette.accent
            )
        }
    }

    @ViewBuilder
    private var urgentSignals: some View {
        if !dashboard.snapshot.signals.isEmpty {
            VStack(alignment: .leading, spacing: 10) {
                sectionTitle("Требует внимания", subtitle: "Сначала показаны наиболее срочные сигналы")
                ForEach(dashboard.snapshot.signals.prefix(5)) { signal in
                    HStack(alignment: .top, spacing: 12) {
                        Image(
                            systemName: signal.requiresApproval
                                ? "checkmark.seal.fill"
                                : "bell.badge.fill"
                        )
                        .foregroundStyle(signalColor(signal.priority))
                        .frame(width: 24)

                        VStack(alignment: .leading, spacing: 4) {
                            Text(signal.title)
                                .font(.subheadline.weight(.semibold))
                            Text(signal.body)
                                .font(.caption)
                                .foregroundStyle(JafarPalette.secondaryText)
                            if let dueDate = signal.dueDate {
                                Label(dueDate, systemImage: "calendar")
                                    .font(.caption2.monospacedDigit())
                                    .foregroundStyle(signalColor(signal.priority))
                            }
                        }
                        Spacer(minLength: 0)
                    }
                    .jafarCard()
                }
            }
        }
    }

    private var matters: some View {
        VStack(alignment: .leading, spacing: 10) {
            sectionTitle("Дела", subtitle: "Реальное состояние backend-хранилища")

            if dashboard.snapshot.matters.isEmpty {
                Label("В backend пока нет активных дел", systemImage: "tray")
                    .font(.subheadline)
                    .foregroundStyle(JafarPalette.secondaryText)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .jafarCard()
            } else {
                ForEach(dashboard.snapshot.matters) { matter in
                    VStack(alignment: .leading, spacing: 10) {
                        HStack(alignment: .firstTextBaseline) {
                            Text(matter.title)
                                .font(.headline)
                            Spacer()
                            Text(matter.status.uppercased())
                                .font(.caption2.weight(.bold))
                                .foregroundStyle(JafarPalette.success)
                        }

                        if let caseNumber = matter.caseNumber, !caseNumber.isEmpty {
                            Label(caseNumber, systemImage: "number")
                                .font(.caption)
                                .foregroundStyle(JafarPalette.secondaryText)
                                .textSelection(.enabled)
                        }

                        if let clientName = matter.clientName, !clientName.isEmpty {
                            Label(clientName, systemImage: "person.fill")
                                .font(.caption)
                                .foregroundStyle(JafarPalette.secondaryText)
                        }

                        Divider()
                            .overlay(Color.white.opacity(0.08))

                        HStack {
                            Label(
                                "Сроков: \(matter.deadlineCount)",
                                systemImage: "calendar"
                            )
                            .foregroundStyle(JafarPalette.secondaryText)

                            if matter.overdueDeadlineCount > 0 {
                                Label(
                                    "Просрочено: \(matter.overdueDeadlineCount)",
                                    systemImage: "exclamationmark.triangle.fill"
                                )
                                .foregroundStyle(JafarPalette.danger)
                            }
                            Spacer(minLength: 0)
                        }
                        .font(.caption)

                        if let nextTitle = matter.nextDeadlineTitle,
                           let nextDate = matter.nextDeadlineDate {
                            Text("Следующий срок: \(nextDate) — \(nextTitle)")
                                .font(.caption)
                                .foregroundStyle(JafarPalette.warning)
                        }
                    }
                    .jafarCard()
                }
            }
        }
    }

    private func metricCard(
        _ title: String,
        value: Int,
        icon: String,
        color: Color
    ) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Image(systemName: icon)
                .foregroundStyle(color)
            Text("\(value)")
                .font(.title2.monospacedDigit().weight(.bold))
            Text(title)
                .font(.caption)
                .foregroundStyle(JafarPalette.secondaryText)
        }
        .frame(maxWidth: .infinity, minHeight: 105, alignment: .topLeading)
        .jafarCard()
    }

    private func sectionTitle(_ title: String, subtitle: String) -> some View {
        VStack(alignment: .leading, spacing: 3) {
            Text(title)
                .font(.title3.weight(.bold))
            Text(subtitle)
                .font(.caption)
                .foregroundStyle(JafarPalette.secondaryText)
        }
    }

    private func signalColor(_ priority: Int) -> Color {
        if priority >= 80 { return JafarPalette.danger }
        if priority >= 50 { return JafarPalette.warning }
        return JafarPalette.accent
    }
}
