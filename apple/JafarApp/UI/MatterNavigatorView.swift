import SwiftUI

struct MatterNavigatorView: View {
    @Environment(\.dismiss) private var dismiss
    @ObservedObject var dashboard: DashboardStore
    @State private var selectedMatter: DashboardMatter?

    var body: some View {
        NavigationStack {
            ZStack {
                JafarPalette.background.ignoresSafeArea()

                if dashboard.snapshot.matters.isEmpty {
                    ContentUnavailableView(
                        "Нет дел",
                        systemImage: "briefcase",
                        description: Text("В подключённом backend пока нет карточек дел.")
                    )
                } else {
                    List(dashboard.snapshot.matters) { matter in
                        Button {
                            selectedMatter = matter
                        } label: {
                            matterRow(matter)
                        }
                        .buttonStyle(.plain)
                        .listRowBackground(JafarPalette.card)
                    }
                    .scrollContentBackground(.hidden)
                }
            }
            .navigationTitle("Дела")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Закрыть") { dismiss() }
                }
                ToolbarItem(placement: .primaryAction) {
                    Button {
                        Task { await dashboard.refresh() }
                    } label: {
                        Image(systemName: "arrow.clockwise")
                    }
                    .disabled(dashboard.isLoading)
                    .accessibilityLabel("Обновить список дел")
                }
            }
        }
        .sheet(item: $selectedMatter) { matter in
            MatterDetailView(
                summary: matter,
                client: JafarClientFactory.matterDetailClient()
            )
        }
        .preferredColorScheme(.dark)
    }

    private func matterRow(_ matter: DashboardMatter) -> some View {
        HStack(alignment: .top, spacing: 12) {
            Image(systemName: "briefcase.fill")
                .foregroundStyle(matter.overdueDeadlineCount > 0 ? JafarPalette.danger : JafarPalette.accent)
                .frame(width: 28)

            VStack(alignment: .leading, spacing: 5) {
                HStack(alignment: .firstTextBaseline) {
                    Text(matter.title)
                        .font(.headline)
                        .foregroundStyle(.primary)
                    Spacer(minLength: 8)
                    Text(matter.status.uppercased())
                        .font(.caption2.weight(.bold))
                        .foregroundStyle(matter.status.caseInsensitiveCompare("active") == .orderedSame ? JafarPalette.success : JafarPalette.secondaryText)
                }

                if let caseNumber = matter.caseNumber, !caseNumber.isEmpty {
                    Label(caseNumber, systemImage: "number")
                        .font(.caption)
                        .foregroundStyle(JafarPalette.secondaryText)
                }
                if let clientName = matter.clientName, !clientName.isEmpty {
                    Label(clientName, systemImage: "person.fill")
                        .font(.caption)
                        .foregroundStyle(JafarPalette.secondaryText)
                }

                HStack(spacing: 12) {
                    Label("Сроков: \(matter.deadlineCount)", systemImage: "calendar")
                    if matter.overdueDeadlineCount > 0 {
                        Label("Просрочено: \(matter.overdueDeadlineCount)", systemImage: "exclamationmark.triangle.fill")
                            .foregroundStyle(JafarPalette.danger)
                    }
                }
                .font(.caption2)
                .foregroundStyle(JafarPalette.secondaryText)
            }

            Image(systemName: "chevron.right")
                .font(.caption.weight(.semibold))
                .foregroundStyle(JafarPalette.secondaryText)
                .padding(.top, 4)
        }
        .padding(.vertical, 7)
    }
}

private struct MatterDetailView: View {
    @Environment(\.dismiss) private var dismiss
    let summary: DashboardMatter
    let client: any MatterDetailClient

    @State private var snapshot: MatterWorkspaceSnapshot?
    @State private var isLoading = false
    @State private var errorMessage: String?

    var body: some View {
        NavigationStack {
            ZStack {
                JafarPalette.background.ignoresSafeArea()

                Group {
                    if let snapshot {
                        ScrollView {
                            VStack(alignment: .leading, spacing: 16) {
                                identityCard(snapshot.matter)
                                deadlineSection(snapshot.matter.deadlines)
                                timelineSection(snapshot.events)
                                provenanceNotice
                            }
                            .frame(maxWidth: 820)
                            .padding(18)
                            .frame(maxWidth: .infinity)
                        }
                    } else if isLoading {
                        ProgressView("Загружаю дело…")
                    } else {
                        ContentUnavailableView(
                            "Не удалось открыть дело",
                            systemImage: "exclamationmark.triangle",
                            description: Text(errorMessage ?? "Данные дела недоступны.")
                        )
                    }
                }
            }
            .navigationTitle(summary.title)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Закрыть") { dismiss() }
                }
                ToolbarItem(placement: .primaryAction) {
                    Button {
                        Task { await load() }
                    } label: {
                        Image(systemName: "arrow.clockwise")
                    }
                    .disabled(isLoading)
                    .accessibilityLabel("Обновить дело")
                }
            }
        }
        .task { await load() }
        .preferredColorScheme(.dark)
    }

    private func identityCard(_ matter: MatterDetail) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Label("Карточка дела", systemImage: "briefcase.fill")
                    .font(.headline)
                    .foregroundStyle(JafarPalette.accent)
                Spacer()
                Text(matter.status.uppercased())
                    .font(.caption.weight(.bold))
                    .foregroundStyle(matter.status.caseInsensitiveCompare("active") == .orderedSame ? JafarPalette.success : JafarPalette.secondaryText)
            }

            Text(matter.title)
                .font(.title3.weight(.bold))
                .textSelection(.enabled)

            detailLine("Тип", matter.matterType)
            detailLine("Клиент", matter.clientName)
            detailLine("Номер дела", matter.caseNumber)
            detailLine("Суд / орган", matter.courtOrAuthority)
            detailLine("Оппонент", matter.opposingParty)
        }
        .jafarCard()
    }

    @ViewBuilder
    private func deadlineSection(_ deadlines: [MatterDeadline]) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            sectionHeader("Сроки", icon: "calendar.badge.clock")

            if deadlines.isEmpty {
                Text("Зафиксированных сроков нет.")
                    .font(.subheadline)
                    .foregroundStyle(JafarPalette.secondaryText)
                    .jafarCard()
            } else {
                ForEach(deadlines) { deadline in
                    VStack(alignment: .leading, spacing: 6) {
                        HStack {
                            Text(deadline.title)
                                .font(.subheadline.weight(.semibold))
                            Spacer()
                            if let dueDate = deadline.dueDate {
                                Text(dueDate)
                                    .font(.caption.monospacedDigit())
                                    .foregroundStyle(JafarPalette.warning)
                            }
                        }
                        if let source = deadline.sourceText, !source.isEmpty {
                            Text(source)
                                .font(.caption)
                                .foregroundStyle(JafarPalette.secondaryText)
                                .textSelection(.enabled)
                        }
                        ProgressView(value: min(max(deadline.confidence, 0), 1))
                        Text("Уверенность извлечения: \(Int(deadline.confidence * 100))%")
                            .font(.caption2)
                            .foregroundStyle(JafarPalette.secondaryText)
                    }
                    .jafarCard()
                }
            }
        }
    }

    @ViewBuilder
    private func timelineSection(_ events: [MatterTimelineEvent]) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            sectionHeader("Хронология", icon: "clock.arrow.circlepath")

            if events.isEmpty {
                Text("События по делу ещё не зафиксированы.")
                    .font(.subheadline)
                    .foregroundStyle(JafarPalette.secondaryText)
                    .jafarCard()
            } else {
                ForEach(events.reversed()) { event in
                    VStack(alignment: .leading, spacing: 6) {
                        HStack(alignment: .firstTextBaseline) {
                            Text(event.title)
                                .font(.subheadline.weight(.semibold))
                            Spacer(minLength: 8)
                            Text(event.eventDate)
                                .font(.caption2.monospacedDigit())
                                .foregroundStyle(JafarPalette.secondaryText)
                        }
                        if let description = event.description, !description.isEmpty {
                            Text(description)
                                .font(.caption)
                                .foregroundStyle(JafarPalette.secondaryText)
                                .textSelection(.enabled)
                        }
                        if let sourceDocument = event.sourceDocument, !sourceDocument.isEmpty {
                            Label(sourceDocument, systemImage: "doc.fill")
                                .font(.caption2)
                                .foregroundStyle(JafarPalette.accent)
                        }
                    }
                    .jafarCard()
                }
            }
        }
    }

    private var provenanceNotice: some View {
        Label(
            "Экран только читает сохранённое состояние дела. Анализ документов не изменяет карточку, сроки или хронологию без отдельного одобренного действия.",
            systemImage: "lock.shield.fill"
        )
        .font(.caption)
        .foregroundStyle(JafarPalette.secondaryText)
        .jafarCard()
    }

    private func sectionHeader(_ title: String, icon: String) -> some View {
        Label(title, systemImage: icon)
            .font(.title3.weight(.bold))
            .foregroundStyle(.primary)
    }

    @ViewBuilder
    private func detailLine(_ label: String, _ value: String?) -> some View {
        if let value, !value.isEmpty {
            HStack(alignment: .top) {
                Text(label)
                    .font(.caption)
                    .foregroundStyle(JafarPalette.secondaryText)
                    .frame(width: 92, alignment: .leading)
                Text(value)
                    .font(.subheadline)
                    .textSelection(.enabled)
                Spacer(minLength: 0)
            }
        }
    }

    @MainActor
    private func load() async {
        guard !isLoading else { return }
        isLoading = true
        defer { isLoading = false }
        do {
            snapshot = try await client.fetchMatter(summary.id)
            errorMessage = nil
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}
