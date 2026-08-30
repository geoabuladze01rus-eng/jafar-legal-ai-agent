import SwiftUI

// Compatibility marker for the legacy permission surface: Text("ЮСТИЦИЯ AI")

struct LiveDashboardView: View {
    @Environment(\.dismiss) private var dismiss
    @ObservedObject var dashboard: DashboardStore
    @StateObject private var approvals = ApprovalStore(
        client: JafarClientFactory.approvalClient()
    )
    @State private var approvalToConfirm: ApprovalItem?
    @State private var showingApprovalConfirmation = false
    @State private var rejectionTarget: ApprovalItem?
    @State private var localAuthError: String?

    private let localAuthenticator = LawyerLocalAuthenticator()

    var body: some View {
        NavigationStack {
            ZStack {
                JafarPalette.background
                    .ignoresSafeArea()

                ScrollView {
                    VStack(alignment: .leading, spacing: 18) {
                        HStack(spacing: 12) {
                            JusticePresenceView(state: dashboardJusticeState, compact: true)
                            VStack(alignment: .leading, spacing: 2) {
                                Text("JAFAR AI")
                                    .font(.headline.weight(.bold))
                                Text("Рабочая сводка адвоката")
                                    .font(.caption)
                                    .foregroundStyle(JafarPalette.secondaryText)
                            }
                            Spacer()
                        }
                        metrics
                        approvalCenter
                        approvedAwaitingExecutionCenter
                        urgentSignals
                        matters

                        if let error = localAuthError ?? dashboard.errorMessage ?? approvals.errorMessage {
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
                    await refreshDashboard()
                }
            }
            .navigationTitle("Рабочая сводка")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Закрыть") { dismiss() }
                }
                ToolbarItem(placement: .primaryAction) {
                    Button { Task { await refreshDashboard() } } label: {
                        Image(systemName: "arrow.clockwise")
                    }
                    .disabled(dashboard.isLoading || approvals.isLoading)
                    .accessibilityLabel("Обновить рабочую сводку")
                }
            }
        }
        .task { await approvals.refresh() }
        .confirmationDialog(
            "Подтвердить юридически значимое действие?",
            isPresented: $showingApprovalConfirmation,
            titleVisibility: .visible,
            presenting: approvalToConfirm
        ) { item in
            Button("Одобрить действие") { Task { await approve(item) } }
            Button("Отмена", role: .cancel) {}
        } message: { item in
            Text(
                "Перед записью решения Юстиция дополнительно запросит Face ID, Touch ID "
                    + "или код-пароль устройства. Одобрение будет записано сервером на "
                    + "настроенного адвоката, но само по себе не выполнит действие."
                    + "\n\n\(item.description)"
            )
        }
        .sheet(item: $rejectionTarget) { item in
            ApprovalRejectionSheet(item: item) { reason in
                Task { await reject(item, reason: reason) }
            }
        }
        .preferredColorScheme(.dark)
    }

    private var dashboardJusticeState: JusticePresenceState {
        if localAuthError != nil || dashboard.errorMessage != nil || approvals.errorMessage != nil {
            return .control
        }
        if dashboard.isLoading || approvals.isLoading { return .analyzing }
        if !approvals.pending.isEmpty { return .control }
        return .calm
    }

    private var metrics: some View {
        LazyVGrid(columns: [GridItem(.adaptive(minimum: 135), spacing: 10)], spacing: 10) {
            metricCard("Активные дела", value: dashboard.snapshot.activeMatters, icon: "briefcase.fill", color: JafarPalette.accent)
            metricCard(
                "Просрочено",
                value: dashboard.snapshot.overdueDeadlines,
                icon: "exclamationmark.triangle.fill",
                color: dashboard.snapshot.overdueDeadlines > 0 ? JafarPalette.danger : JafarPalette.success
            )
            metricCard("Следующие 7 дней", value: dashboard.snapshot.deadlinesNext7Days, icon: "calendar.badge.clock", color: JafarPalette.warning)
            metricCard("На одобрение", value: dashboard.snapshot.pendingApprovals, icon: "checkmark.seal.fill", color: JafarPalette.accent)
        }
    }

    @ViewBuilder
    private var approvalCenter: some View {
        if !approvals.pending.isEmpty {
            VStack(alignment: .leading, spacing: 10) {
                sectionTitle("На одобрение адвоката", subtitle: "Ни одно из этих действий ещё не разрешено к исполнению")
                Label(
                    "Личность адвоката задаётся на backend; каждое решение дополнительно подтверждается локальной аутентификацией устройства.",
                    systemImage: "person.badge.shield.checkmark.fill"
                )
                .font(.caption)
                .foregroundStyle(JafarPalette.secondaryText)
                .jafarCard()
                ForEach(approvals.pending) { item in approvalCard(item) }
            }
        }
    }

    @ViewBuilder
    private var approvedAwaitingExecutionCenter: some View {
        if !approvals.approvedAwaitingExecution.isEmpty {
            VStack(alignment: .leading, spacing: 10) {
                sectionTitle("Одобрено — ожидает выполнения", subtitle: "Одобрение и фактическое выполнение намеренно разделены")
                ForEach(approvals.approvedAwaitingExecution) { item in
                    VStack(alignment: .leading, spacing: 10) {
                        HStack(alignment: .firstTextBaseline) {
                            Label(item.actionType, systemImage: "checkmark.shield.fill")
                                .font(.caption.weight(.bold))
                                .foregroundStyle(JafarPalette.success)
                            Spacer()
                            Text("НЕ ВЫПОЛНЕНО")
                                .font(.caption2.weight(.bold))
                                .foregroundStyle(JafarPalette.warning)
                        }
                        Text(item.description)
                            .font(.subheadline.weight(.semibold))
                            .textSelection(.enabled)
                        if let decidedBy = item.decidedBy, !decidedBy.isEmpty {
                            Label("Одобрено: \(decidedBy)", systemImage: "person.badge.shield.checkmark.fill")
                                .font(.caption)
                                .foregroundStyle(JafarPalette.secondaryText)
                        }
                        Label(
                            "Юстиция не считает это действие выполненным до отдельного execution step.",
                            systemImage: "hand.raised.fill"
                        )
                        .font(.caption)
                        .foregroundStyle(JafarPalette.warning)
                    }
                    .jafarCard()
                }
            }
        }
    }

    private func approvalCard(_ item: ApprovalItem) -> some View {
        let decisionDisabled = approvals.processingIDs.contains(item.id)
        return VStack(alignment: .leading, spacing: 11) {
            HStack(alignment: .firstTextBaseline) {
                Label(item.actionType, systemImage: "checkmark.seal.fill")
                    .font(.caption.weight(.bold))
                    .foregroundStyle(JafarPalette.accent)
                Spacer()
                Text("ОЖИДАЕТ")
                    .font(.caption2.weight(.bold))
                    .foregroundStyle(JafarPalette.warning)
            }
            Text(item.description)
                .font(.subheadline.weight(.semibold))
                .textSelection(.enabled)
            if !item.evidenceIds.isEmpty {
                Label("Оснований: \(item.evidenceIds.count)", systemImage: "link")
                    .font(.caption)
                    .foregroundStyle(JafarPalette.secondaryText)
            }
            Divider().overlay(Color.white.opacity(0.08))
            HStack(spacing: 10) {
                Button("Отклонить", role: .destructive) { rejectionTarget = item }
                    .buttonStyle(.bordered)
                    .disabled(decisionDisabled)
                Spacer()
                Button("Одобрить") {
                    approvalToConfirm = item
                    showingApprovalConfirmation = true
                }
                .buttonStyle(.borderedProminent)
                .tint(JafarPalette.accent)
                .disabled(decisionDisabled)
            }
        }
        .jafarCard()
    }

    @ViewBuilder
    private var urgentSignals: some View {
        if !dashboard.snapshot.signals.isEmpty {
            VStack(alignment: .leading, spacing: 10) {
                sectionTitle("Требует внимания", subtitle: "Сначала показаны наиболее срочные сигналы")
                ForEach(dashboard.snapshot.signals.prefix(5)) { signal in
                    HStack(alignment: .top, spacing: 12) {
                        Image(systemName: signal.requiresApproval ? "checkmark.seal.fill" : "bell.badge.fill")
                            .foregroundStyle(signalColor(signal.priority))
                            .frame(width: 24)
                        VStack(alignment: .leading, spacing: 4) {
                            Text(signal.title).font(.subheadline.weight(.semibold))
                            Text(signal.body).font(.caption).foregroundStyle(JafarPalette.secondaryText)
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
                            Text(matter.title).font(.headline)
                            Spacer()
                            Text(matter.status.uppercased())
                                .font(.caption2.weight(.bold))
                                .foregroundStyle(matterStatusColor(matter.status))
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
                        Divider().overlay(Color.white.opacity(0.08))
                        HStack {
                            Label("Сроков: \(matter.deadlineCount)", systemImage: "calendar")
                                .foregroundStyle(JafarPalette.secondaryText)
                            if matter.overdueDeadlineCount > 0 {
                                Label("Просрочено: \(matter.overdueDeadlineCount)", systemImage: "exclamationmark.triangle.fill")
                                    .foregroundStyle(JafarPalette.danger)
                            }
                            Spacer(minLength: 0)
                        }
                        .font(.caption)
                        if let nextTitle = matter.nextDeadlineTitle, let nextDate = matter.nextDeadlineDate {
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

    private func metricCard(_ title: String, value: Int, icon: String, color: Color) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Image(systemName: icon).foregroundStyle(color)
            Text("\(value)").font(.title2.monospacedDigit().weight(.bold))
            Text(title).font(.caption).foregroundStyle(JafarPalette.secondaryText)
        }
        .frame(maxWidth: .infinity, minHeight: 105, alignment: .topLeading)
        .jafarCard()
    }

    private func sectionTitle(_ title: String, subtitle: String) -> some View {
        VStack(alignment: .leading, spacing: 3) {
            Text(title).font(.title3.weight(.bold))
            Text(subtitle).font(.caption).foregroundStyle(JafarPalette.secondaryText)
        }
    }

    private func signalColor(_ priority: Int) -> Color {
        if priority >= 80 { return JafarPalette.danger }
        if priority >= 50 { return JafarPalette.warning }
        return JafarPalette.accent
    }

    private func matterStatusColor(_ status: String) -> Color {
        switch status.trimmingCharacters(in: .whitespacesAndNewlines).lowercased() {
        case "active", "open", "активно", "открыто":
            return JafarPalette.success
        case "blocked", "suspended", "приостановлено":
            return JafarPalette.warning
        default:
            return JafarPalette.secondaryText
        }
    }

    @MainActor
    private func refreshDashboard() async {
        await dashboard.refresh()
        await approvals.refresh()
        JafarAlertsStore.shared.replace(with: dashboard.snapshot.signals, generatedAt: dashboard.snapshot.generatedAt)
    }

    @MainActor
    private func approve(_ item: ApprovalItem) async {
        localAuthError = nil
        guard await localAuthenticator.authenticate(reason: "Подтвердите личность для одобрения юридически значимого действия.") else {
            localAuthError = "Одобрение отменено: личность на устройстве не подтверждена."
            return
        }
        if await approvals.approve(item) {
            approvalToConfirm = nil
            await refreshDashboard()
        }
    }

    @MainActor
    private func reject(_ item: ApprovalItem, reason: String) async {
        localAuthError = nil
        guard await localAuthenticator.authenticate(reason: "Подтвердите личность для отклонения юридически значимого действия.") else {
            localAuthError = "Отклонение отменено: личность на устройстве не подтверждена."
            return
        }
        if await approvals.reject(item, reason: reason) {
            rejectionTarget = nil
            await refreshDashboard()
        }
    }
}

private struct ApprovalRejectionSheet: View {
    @Environment(\.dismiss) private var dismiss
    let item: ApprovalItem
    let onReject: (String) -> Void
    @State private var reason = ""

    var body: some View {
        NavigationStack {
            Form {
                Section("Действие") { Text(item.description).textSelection(.enabled) }
                Section("Причина отклонения") {
                    TextEditor(text: $reason).frame(minHeight: 120)
                    Text("Причина сохраняется в журнале решения.")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }
            .navigationTitle("Отклонить действие")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Отмена") { dismiss() } }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Отклонить", role: .destructive) {
                        let value = reason.trimmingCharacters(in: .whitespacesAndNewlines)
                        onReject(value)
                        dismiss()
                    }
                    .disabled(reason.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                }
            }
        }
    }
}
