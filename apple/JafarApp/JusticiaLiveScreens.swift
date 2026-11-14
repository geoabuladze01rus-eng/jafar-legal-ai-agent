import Foundation
import SwiftUI
import UniformTypeIdentifiers

struct JusticiaLiveHomeView: View {
    @ObservedObject var workspace: JusticiaWorkspaceStore
    let navigate: (JusticiaSection) -> Void
    let canCreateMatter: Bool
    let createMatter: () -> Void

    @State private var selectionTask: Task<Void, Never>?
    @State private var showsGettingStarted = false
    @State private var deadlineScope: DeadlineScope = .upcoming

    private enum DeadlineScope: String, CaseIterable {
        case upcoming = "Предстоящие"
        case overdue = "Просроченные"
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 22) {
            HStack(alignment: .center, spacing: 18) {
                pageHeader(title: "Рабочий стол", subtitle: "Дела, документы и процессуальные сроки.")
                if !workspace.matters.isEmpty {
                    newMatterButton("Новое дело")
                        .fixedSize()
                }
            }

            if workspace.isLoading && workspace.matters.isEmpty {
                ProgressView("Открываем рабочий стол…")
                    .frame(maxWidth: .infinity, minHeight: 170)
                    .justiciaCard()
            } else {
                if let error = workspace.errorMessage {
                    errorCard(error)
                }
                if workspace.matters.isEmpty && workspace.errorMessage == nil {
                    firstMatterCard
                } else if !workspace.matters.isEmpty {
                    if let matter = workspace.selectedMatter {
                        activeMatter(matter)
                    }
                    ViewThatFits(in: .horizontal) {
                        HStack(alignment: .top, spacing: 16) {
                            recentMatters.frame(minWidth: 340)
                            deadlines.frame(minWidth: 300)
                        }
                        VStack(spacing: 16) {
                            recentMatters
                            deadlines
                        }
                    }
                }
            }
        }
        .onDisappear {
            selectionTask?.cancel()
            selectionTask = nil
        }
    }

    private var firstMatterCard: some View {
        ViewThatFits(in: .horizontal) {
            HStack(spacing: 30) {
                welcomeMessage.frame(minWidth: 330)
                Spacer(minLength: 0)
                ZStack {
                    Circle().strokeBorder(JusticiaTheme.gold.opacity(0.18))
                    Circle()
                        .fill(JusticiaTheme.gold.opacity(0.07))
                        .padding(14)
                    JusticiaScalesMark()
                        .stroke(JusticiaTheme.gold, style: StrokeStyle(lineWidth: 1.5, lineCap: .round, lineJoin: .round))
                        .frame(width: 79, height: 79)
                }
                .frame(width: 162, height: 162)
                .accessibilityHidden(true)
            }
            VStack(alignment: .leading) { welcomeMessage }
        }
        .padding(30)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background {
            RoundedRectangle(cornerRadius: JusticiaTheme.largeCorner)
                .fill(LinearGradient(colors: [JusticiaTheme.surface, JusticiaTheme.surfaceMuted],
                                     startPoint: .topLeading, endPoint: .bottomTrailing))
        }
        .overlay {
            RoundedRectangle(cornerRadius: JusticiaTheme.largeCorner)
                .strokeBorder(JusticiaTheme.border)
                .allowsHitTesting(false)
        }
    }

    private var welcomeMessage: some View {
        VStack(alignment: .leading, spacing: 11) {
            Text("Создайте первое дело")
                .font(.system(size: 33, weight: .semibold, design: .serif))
                .foregroundStyle(JusticiaTheme.ink)
                .accessibilityAddTraits(.isHeader)
            Text("В карточку дела можно загрузить материалы, проверить документы и подготовить черновик.")
                .font(.subheadline)
                .foregroundStyle(JusticiaTheme.secondaryInk)
                .lineSpacing(3)
                .fixedSize(horizontal: false, vertical: true)
                .frame(maxWidth: 390, alignment: .leading)
            if canCreateMatter {
                newMatterButton("Создать первое дело")
                    .padding(.top, 7)
                Label("Материалы хранятся на этом устройстве", systemImage: "lock.shield")
                    .font(.caption)
                    .foregroundStyle(JusticiaTheme.secondaryInk)
                    .padding(.top, 3)
                DisclosureGroup("Как начать работу", isExpanded: $showsGettingStarted) {
                    VStack(alignment: .leading, spacing: 8) {
                        Label("Создайте карточку дела.", systemImage: "briefcase")
                        Label("Загрузите PDF или Word в разделе «Документы».", systemImage: "doc.on.doc")
                        Label("Подготовьте проект в разделе «Шаблоны».", systemImage: "pencil.and.outline")
                    }
                    .font(.caption)
                    .foregroundStyle(JusticiaTheme.secondaryInk)
                    .padding(.top, 8)
                }
                .font(.subheadline.weight(.medium))
                .frame(maxWidth: 390, alignment: .leading)
            }
        }
    }

    private func newMatterButton(_ title: String) -> some View {
        Button(action: createMatter) { Label(title, systemImage: "plus") }
            .buttonStyle(.borderedProminent)
            .controlSize(.large)
            .disabled(!canCreateMatter)
    }

    private func activeMatter(_ matter: JusticiaMatterDTO) -> some View {
        VStack(alignment: .leading, spacing: 13) {
            HStack {
                Label("Выбранное дело", systemImage: "briefcase")
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(JusticiaTheme.secondaryInk)
                Spacer(minLength: 12)
                Picker("Выбранное дело", selection: Binding(
                    get: { workspace.selectedMatterID },
                    set: { id in
                        guard let next = workspace.matters.first(where: { $0.id == id }) else { return }
                        selectMatter(next)
                    }
                )) {
                    ForEach(workspace.matters) { option in
                        Text(option.title).tag(Optional(option.id))
                    }
                }
                .labelsHidden()
                .pickerStyle(.menu)
                .frame(maxWidth: 280)
                .disabled(selectionTask != nil)
            }
            Text(matter.title)
                .font(.system(.title2, design: .serif, weight: .semibold))
                .foregroundStyle(JusticiaTheme.ink)
                .accessibilityAddTraits(.isHeader)
            Text(matter.displayNumber + " · " + matter.displayStatus)
                .font(.subheadline)
                .foregroundStyle(JusticiaTheme.secondaryInk)
            Divider()
            ViewThatFits(in: .horizontal) {
                HStack(spacing: 10) { matterShortcuts }
                VStack(alignment: .leading, spacing: 8) { matterShortcuts }
            }
            .disabled(selectionTask != nil)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .justiciaCard(padding: 20)
    }

    @ViewBuilder
    private var matterShortcuts: some View {
        shortcut("Карточка", icon: "briefcase", section: .matters)
        shortcut("Документы", icon: "doc.on.doc", section: .documents)
        shortcut("Черновики", icon: "square.and.pencil", section: .templates)
    }

    private func shortcut(_ title: String, icon: String, section: JusticiaSection) -> some View {
        Button { navigate(section) } label: { Label(title, systemImage: icon) }
            .buttonStyle(.bordered)
            .controlSize(.regular)
    }

    private func selectMatter(_ matter: JusticiaMatterDTO, then section: JusticiaSection? = nil) {
        guard selectionTask == nil else { return }
        selectionTask = Task { @MainActor in
            defer { if !Task.isCancelled { selectionTask = nil } }
            if workspace.selectedMatterID != matter.id {
                await workspace.selectMatter(matter)
            }
            guard !Task.isCancelled else { return }
            if let section { navigate(section) }
        }
    }

    private var recentMatters: some View {
        let recent = Array(workspace.matters.sorted { $0.updatedAt > $1.updatedAt }.prefix(5))
        return VStack(alignment: .leading, spacing: 0) {
            sectionTitle("Последние дела", action: "Все дела") { navigate(.matters) }
                .padding(.bottom, 12)
            ForEach(recent) { matter in
                Divider()
                Button {
                    selectMatter(matter, then: .matters)
                } label: {
                    HStack(spacing: 11) {
                        JusticiaIconTile(systemName: "briefcase", size: 32)
                        VStack(alignment: .leading, spacing: 4) {
                            Text(matter.title)
                                .font(.subheadline.weight(.semibold))
                                .foregroundStyle(JusticiaTheme.ink)
                                .lineLimit(2)
                            Text(matter.displayNumber)
                                .font(.caption)
                                .foregroundStyle(JusticiaTheme.secondaryInk)
                        }
                        Spacer(minLength: 6)
                        JusticiaPill(text: matter.displayStatus, color: JusticiaTheme.blue)
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.vertical, 11)
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .disabled(selectionTask != nil)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .justiciaCard(padding: 19)
    }

    private var deadlines: some View {
        let dateParser = DateFormatter()
        dateParser.locale = Locale(identifier: "en_US_POSIX")
        dateParser.calendar = Calendar(identifier: .gregorian)
        dateParser.dateFormat = "yyyy-MM-dd"
        dateParser.isLenient = false
        let today = dateParser.string(from: Date())
        let datedDeadlines = workspace.matters.filter { $0.status.lowercased() != "closed" }.flatMap { matter in
            matter.deadlines.compactMap { deadline in
                deadline.dueDate.map { (date: $0, title: deadline.title, matter: matter) }
            }
        }.filter { item in
            deadlineScope == .overdue ? item.date < today : item.date >= today
        }.sorted { lhs, rhs in
            deadlineScope == .overdue ? lhs.date > rhs.date : lhs.date < rhs.date
        }
        let preview = Array(datedDeadlines.prefix(5))
        return VStack(alignment: .leading, spacing: 0) {
            sectionTitle("Сроки по делам", action: "Все сроки") { navigate(.deadlines) }
                .padding(.bottom, 12)
            Picker("Период сроков", selection: $deadlineScope) {
                ForEach(DeadlineScope.allCases, id: \.self) { scope in
                    Text(scope.rawValue).tag(scope)
                }
            }
            .pickerStyle(.segmented)
            .labelsHidden()
            .padding(.bottom, 12)
            if preview.isEmpty {
                Divider()
                Text(deadlineScope == .overdue ? "Просроченных сроков нет." : "Предстоящих сроков нет.")
                    .font(.subheadline)
                    .foregroundStyle(JusticiaTheme.secondaryInk)
                    .padding(.top, 14)
            } else {
                ForEach(Array(preview.enumerated()), id: \.offset) { _, item in
                    Divider()
                    Button {
                        selectMatter(item.matter, then: .matters)
                    } label: {
                        HStack(spacing: 11) {
                            JusticiaIconTile(systemName: "calendar", color: JusticiaTheme.gold, size: 32)
                            VStack(alignment: .leading, spacing: 4) {
                                Text(item.title)
                                    .font(.subheadline.weight(.semibold))
                                    .foregroundStyle(JusticiaTheme.ink)
                                    .lineLimit(2)
                                Text(item.matter.displayNumber)
                                    .font(.caption)
                                    .foregroundStyle(JusticiaTheme.secondaryInk)
                            }
                            Spacer(minLength: 6)
                            Text(dateParser.date(from: item.date)?.formatted(.dateTime.day().month().year().locale(Locale(identifier: "ru_RU"))) ?? item.date)
                                .font(.caption.monospacedDigit())
                                .foregroundStyle(JusticiaTheme.secondaryInk)
                            Image(systemName: "chevron.right")
                                .font(.caption2)
                                .foregroundStyle(JusticiaTheme.secondaryInk)
                        }
                        .padding(.vertical, 11)
                        .contentShape(Rectangle())
                    }
                    .buttonStyle(.plain)
                    .disabled(selectionTask != nil)
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .justiciaCard(padding: 19)
    }

    private func errorCard(_ error: String) -> some View {
        HStack(spacing: 10) {
            Image(systemName: "exclamationmark.triangle")
                .foregroundStyle(JusticiaTheme.red)
            Text(error)
                .font(.subheadline)
            Spacer()
            Button("Повторить") {
                Task { await workspace.refresh() }
            }
            .buttonStyle(.bordered)
        }
        .justiciaCard()
    }
}

struct JusticiaLiveMattersView: View {
    @ObservedObject var workspace: JusticiaWorkspaceStore
    let apiClient: JusticiaAPIClient?
    let createMatter: () -> Void
    let openDocument: (String) -> Void

    @State private var filter = ""
    @State private var showingAssistant = false

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            pageHeader(
                title: "Дела",
                subtitle: "Реальные данные из локального зашифрованного хранилища «Юстиции»."
            )

            HStack(alignment: .top, spacing: 14) {
                VStack(alignment: .leading, spacing: 12) {
                    HStack {
                        Text("Мои дела")
                            .font(.headline)
                        Spacer()
                        Button(action: createMatter) {
                            Label("Новое дело", systemImage: "plus")
                        }
                        .buttonStyle(.borderedProminent)
                        .disabled(apiClient == nil)
                    }

                    HStack {
                        Image(systemName: "magnifyingglass")
                            .foregroundStyle(JusticiaTheme.secondaryInk)
                        TextField("Поиск по делу, клиенту или номеру", text: $filter)
                            .textFieldStyle(.plain)
                    }
                    .padding(.horizontal, 11)
                    .frame(height: 36)
                    .background(JusticiaTheme.surfaceMuted)
                    .clipShape(RoundedRectangle(cornerRadius: 9))

                    if filteredMatters.isEmpty {
                        emptyState(
                            icon: "briefcase",
                            title: workspace.matters.isEmpty ? "Дел пока нет" : "Ничего не найдено",
                            message: workspace.matters.isEmpty
                                ? "Создайте первое дело кнопкой выше."
                                : "Измените поисковый запрос."
                        )
                    } else {
                        ForEach(filteredMatters) { matter in
                            Button {
                                Task { await workspace.selectMatter(matter) }
                            } label: {
                                VStack(alignment: .leading, spacing: 8) {
                                    HStack {
                                        Text(matter.displayNumber)
                                            .font(.subheadline.weight(.semibold))
                                        Spacer()
                                        JusticiaPill(text: matter.displayStatus, color: JusticiaTheme.green)
                                    }
                                    Text(matter.title)
                                        .font(.caption)
                                        .foregroundStyle(JusticiaTheme.secondaryInk)
                                        .multilineTextAlignment(.leading)
                                    HStack {
                                        Text(matter.clientName ?? "Клиент не указан")
                                        Spacer()
                                        Text(matter.nextDeadlineText)
                                    }
                                    .font(.caption2)
                                    .foregroundStyle(JusticiaTheme.secondaryInk)
                                }
                                .padding(12)
                                .background(workspace.selectedMatterID == matter.id ? JusticiaTheme.blueSoft : JusticiaTheme.surfaceMuted.opacity(0.55))
                                .clipShape(RoundedRectangle(cornerRadius: 11))
                            }
                            .buttonStyle(.plain)
                        }
                    }
                }
                .frame(width: 370)
                .justiciaCard()

                matterDetail
                    .frame(maxWidth: .infinity)
            }
        }
        .task {
            if workspace.matters.isEmpty { await workspace.refresh() }
        }
        .sheet(isPresented: $showingAssistant) {
            if let matter = workspace.selectedMatter, let apiClient {
                JusticiaMatterAssistantView(
                    matter: matter,
                    apiClient: apiClient,
                    documents: workspace.documents,
                    onOpenDocument: openDocument
                )
            } else {
                Text("ИИ-помощник недоступен для выбранного дела.")
                    .padding(24)
            }
        }
    }

    private var filteredMatters: [JusticiaMatterDTO] {
        guard !filter.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            return workspace.matters
        }
        let needle = filter.lowercased()
        return workspace.matters.filter {
            $0.title.lowercased().contains(needle)
                || $0.displayNumber.lowercased().contains(needle)
                || ($0.clientName?.lowercased().contains(needle) ?? false)
        }
    }

    @ViewBuilder
    private var matterDetail: some View {
        if let matter = workspace.selectedMatter {
            VStack(alignment: .leading, spacing: 16) {
                HStack(alignment: .top) {
                    VStack(alignment: .leading, spacing: 5) {
                        HStack {
                            Text(matter.displayNumber)
                                .font(.title2.bold())
                            JusticiaPill(text: matter.displayStatus, color: JusticiaTheme.green)
                        }
                        Text(matter.title)
                            .font(.subheadline)
                            .foregroundStyle(JusticiaTheme.secondaryInk)
                    }
                    Spacer()

                    Button {
                        showingAssistant = true
                    } label: {
                        Label("ИИ по делу", systemImage: "sparkles")
                    }
                    .buttonStyle(.borderedProminent)
                    .disabled(apiClient == nil || workspace.documents.isEmpty)
                    .help(
                        workspace.documents.isEmpty
                            ? "Сначала импортируйте документы в выбранное дело."
                            : "Исследовать локальные материалы выбранного дела"
                    )
                }

                HStack(alignment: .top, spacing: 14) {
                    VStack(alignment: .leading, spacing: 11) {
                        Text("Основная информация")
                            .font(.headline)
                        detailRow("Клиент", matter.clientName ?? "Не указан")
                        detailRow("Оппонент", matter.opposingParty ?? "Не указан")
                        detailRow("Суд / орган", matter.displayCourt)
                        detailRow("Категория", localizedMatterType(matter.matterType))
                        detailRow("Статус", matter.displayStatus)
                    }
                    .justiciaCard()
                    .frame(maxWidth: .infinity)

                    VStack(alignment: .leading, spacing: 11) {
                        Text("Сроки")
                            .font(.headline)
                        if matter.deadlines.isEmpty {
                            Text("Процессуальные сроки пока не добавлены.")
                                .font(.subheadline)
                                .foregroundStyle(JusticiaTheme.secondaryInk)
                        } else {
                            ForEach(Array(matter.deadlines.enumerated()), id: \.offset) { _, deadline in
                                HStack(alignment: .top, spacing: 8) {
                                    Circle().fill(JusticiaTheme.orange).frame(width: 8, height: 8).padding(.top, 5)
                                    VStack(alignment: .leading, spacing: 2) {
                                        Text(deadline.title).font(.subheadline.weight(.semibold))
                                        if let dueDate = deadline.dueDate {
                                            Text(dueDate).font(.caption).foregroundStyle(JusticiaTheme.secondaryInk)
                                        }
                                    }
                                    Spacer()
                                }
                            }
                        }
                    }
                    .justiciaCard()
                    .frame(maxWidth: .infinity)
                }

                VStack(alignment: .leading, spacing: 10) {
                    Text("Локальные документы")
                        .font(.headline)
                    if workspace.documents.isEmpty {
                        Text("В деле пока нет импортированных документов.")
                            .font(.subheadline)
                            .foregroundStyle(JusticiaTheme.secondaryInk)
                    } else {
                        ForEach(workspace.documents.prefix(5)) { document in
                            HStack {
                                JusticiaIconTile(systemName: "doc.text", color: JusticiaTheme.blue, size: 32)
                                Text(document.filename).font(.subheadline)
                                Spacer()
                                JusticiaPill(text: document.displayState, color: JusticiaTheme.green)
                            }
                        }
                    }
                }
                .justiciaCard()
            }
            .justiciaCard()
        } else {
            emptyState(
                icon: "briefcase",
                title: "Выберите дело",
                message: "Карточка выбранного дела появится здесь."
            )
            .frame(maxWidth: .infinity, minHeight: 420)
            .justiciaCard()
        }
    }

    private func detailRow(_ key: String, _ value: String) -> some View {
        HStack(alignment: .top) {
            Text(key)
                .foregroundStyle(JusticiaTheme.secondaryInk)
                .frame(width: 120, alignment: .leading)
            Text(value)
                .foregroundStyle(JusticiaTheme.ink)
            Spacer()
        }
        .font(.subheadline)
    }

    private func localizedMatterType(_ type: String) -> String {
        switch type {
        case "criminal": "Уголовное"
        case "arbitration": "Арбитраж"
        case "civil": "Гражданское"
        case "administrative": "Административное"
        default: "Общее"
        }
    }
}

struct JusticiaCreateMatterSheet: View {
    @Environment(\.dismiss) private var dismiss
    @ObservedObject var workspace: JusticiaWorkspaceStore
    let onCreated: () -> Void

    @State private var title = ""
    @State private var matterType = "general"
    @State private var clientName = ""
    @State private var opposingParty = ""
    @State private var court = ""
    @State private var caseNumber = ""
    @State private var isSaving = false

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                Text("Новое дело")
                    .font(.title2.bold())
                Spacer()
                Button {
                    dismiss()
                } label: {
                    Image(systemName: "xmark")
                }
                .buttonStyle(.plain)
            }

            TextField("Название дела", text: $title)
                .textFieldStyle(.roundedBorder)

            Picker("Категория", selection: $matterType) {
                Text("Общее").tag("general")
                Text("Уголовное").tag("criminal")
                Text("Гражданское").tag("civil")
                Text("Арбитраж").tag("arbitration")
                Text("Административное").tag("administrative")
            }

            TextField("Клиент", text: $clientName)
                .textFieldStyle(.roundedBorder)
            TextField("Оппонент / вторая сторона", text: $opposingParty)
                .textFieldStyle(.roundedBorder)
            TextField("Суд или орган", text: $court)
                .textFieldStyle(.roundedBorder)
            TextField("Номер дела", text: $caseNumber)
                .textFieldStyle(.roundedBorder)

            if let error = workspace.errorMessage {
                Text(error)
                    .font(.caption)
                    .foregroundStyle(JusticiaTheme.red)
            }

            Spacer()

            HStack {
                Button("Отмена") { dismiss() }
                    .buttonStyle(.bordered)
                Spacer()
                Button {
                    Task {
                        isSaving = true
                        let saved = await workspace.createMatter(
                            title: title,
                            matterType: matterType,
                            clientName: clientName,
                            opposingParty: opposingParty,
                            courtOrAuthority: court,
                            caseNumber: caseNumber
                        )
                        isSaving = false
                        if saved {
                            onCreated()
                            dismiss()
                        }
                    }
                } label: {
                    if isSaving {
                        ProgressView()
                    } else {
                        Text("Создать дело")
                    }
                }
                .buttonStyle(.borderedProminent)
                .disabled(title.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || isSaving)
            }
        }
        .padding(24)
        .background(JusticiaTheme.canvas)
    }
}

struct JusticiaLiveDocumentsView: View {
    @ObservedObject var workspace: JusticiaWorkspaceStore
    @State private var search = ""
    @State private var showingImporter = false
    @State private var analysisTask = "legal_analysis"

    private var allowedTypes: [UTType] {
        [
            .pdf,
            .plainText,
            .rtf,
            UTType(filenameExtension: "docx") ?? .data
        ]
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            pageHeader(
                title: "Документы",
                subtitle: "Импорт документов напрямую в локальный зашифрованный корпус выбранного дела."
            )

            HStack(alignment: .top, spacing: 14) {
                VStack(alignment: .leading, spacing: 12) {
                    HStack {
                        Text("Документы дела")
                            .font(.headline)
                        Spacer()
                        Button {
                            showingImporter = true
                        } label: {
                            if workspace.isImporting {
                                ProgressView()
                            } else {
                                Label("Загрузить", systemImage: "square.and.arrow.down")
                            }
                        }
                        .buttonStyle(.borderedProminent)
                        .disabled(workspace.selectedMatter == nil || workspace.isImporting)
                    }

                    if let matter = workspace.selectedMatter {
                        HStack {
                            JusticiaIconTile(systemName: "briefcase", color: JusticiaTheme.blue, size: 30)
                            VStack(alignment: .leading, spacing: 2) {
                                Text(matter.displayNumber)
                                    .font(.caption.weight(.semibold))
                                Text(matter.title)
                                    .font(.caption2)
                                    .foregroundStyle(JusticiaTheme.secondaryInk)
                                    .lineLimit(1)
                            }
                        }
                    } else {
                        Text("Сначала выберите или создайте дело.")
                            .font(.caption)
                            .foregroundStyle(JusticiaTheme.orange)
                    }

                    HStack {
                        Image(systemName: "magnifyingglass")
                            .foregroundStyle(JusticiaTheme.secondaryInk)
                        TextField("Поиск по документам", text: $search)
                            .textFieldStyle(.plain)
                    }
                    .padding(.horizontal, 11)
                    .frame(height: 36)
                    .background(JusticiaTheme.surfaceMuted)
                    .clipShape(RoundedRectangle(cornerRadius: 9))

                    if filteredDocuments.isEmpty {
                        emptyState(
                            icon: "doc.text",
                            title: "Документов пока нет",
                            message: workspace.selectedMatter == nil
                                ? "Выберите дело в разделе «Дела»."
                                : "Загрузите PDF, DOCX, RTF или текстовый документ."
                        )
                    } else {
                        ForEach(filteredDocuments) { document in
                            Button {
                                workspace.selectedDocumentID = document.id
                            } label: {
                                HStack(spacing: 11) {
                                    JusticiaIconTile(systemName: "doc.text", color: JusticiaTheme.blue, size: 34)
                                    VStack(alignment: .leading, spacing: 3) {
                                        Text(document.filename)
                                            .font(.subheadline.weight(.semibold))
                                            .foregroundStyle(JusticiaTheme.ink)
                                        Text(byteCount(document.byteCount) + " · " + document.mediaType)
                                            .font(.caption)
                                            .foregroundStyle(JusticiaTheme.secondaryInk)
                                    }
                                    Spacer()
                                    JusticiaPill(text: document.displayState, color: JusticiaTheme.green)
                                }
                                .padding(10)
                                .background(workspace.selectedDocumentID == document.id ? JusticiaTheme.blueSoft : Color.clear)
                                .clipShape(RoundedRectangle(cornerRadius: 10))
                            }
                            .buttonStyle(.plain)
                        }
                    }
                }
                .frame(width: 390)
                .justiciaCard()

                documentDetail
                    .frame(maxWidth: .infinity)
            }
        }
        .task {
            if workspace.matters.isEmpty { await workspace.refresh() }
            else { await workspace.refreshDocuments() }
        }
        .fileImporter(isPresented: $showingImporter, allowedContentTypes: allowedTypes, allowsMultipleSelection: false) { result in
            if case .success(let urls) = result, let url = urls.first {
                Task {
                    _ = await workspace.importDocument(from: url)
                }
            }
        }
    }

    private var filteredDocuments: [JusticiaDocumentDTO] {
        guard !search.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            return workspace.documents
        }
        let needle = search.lowercased()
        return workspace.documents.filter { $0.filename.lowercased().contains(needle) }
    }

    @ViewBuilder
    private var documentDetail: some View {
        if let document = workspace.documents.first(where: { $0.id == workspace.selectedDocumentID }) ?? workspace.documents.first {
            VStack(alignment: .leading, spacing: 18) {
                HStack {
                    JusticiaIconTile(systemName: "doc.text", color: JusticiaTheme.blue)
                    VStack(alignment: .leading, spacing: 3) {
                        Text(document.filename)
                            .font(.title3.bold())
                        Text("Локальный документ · " + byteCount(document.byteCount))
                            .font(.caption)
                            .foregroundStyle(JusticiaTheme.secondaryInk)
                    }
                    Spacer()

                    Picker("", selection: $analysisTask) {
                        Text("Общий анализ").tag("legal_analysis")
                        Text("Риски").tag("risk_review")
                        Text("Сроки").tag("extract_deadlines")
                    }
                    .pickerStyle(.segmented)
                    .frame(width: 270)

                    Button {
                        Task {
                            await workspace.analyzeDocument(document, task: analysisTask)
                        }
                    } label: {
                        if workspace.analyzingDocumentID == document.id {
                            ProgressView()
                        } else {
                            Label("Анализировать", systemImage: "sparkles")
                        }
                    }
                    .buttonStyle(.borderedProminent)
                    .disabled(workspace.analyzingDocumentID != nil)

                    JusticiaPill(text: document.displayState, color: JusticiaTheme.green)
                }

                Divider()

                VStack(alignment: .leading, spacing: 10) {
                    Text("Проверяемая provenance-информация")
                        .font(.headline)
                    metadataRow("Document ID", document.documentId)
                    metadataRow("Fingerprint", document.fingerprint)
                    metadataRow("Тип", document.mediaType)
                    metadataRow("Цитат / чанков", "\(document.citations.count)")
                }

                if document.citations.isEmpty {
                    Text("Цитаты появятся после успешной индексации документа.")
                        .font(.subheadline)
                        .foregroundStyle(JusticiaTheme.secondaryInk)
                } else {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Цитаты")
                            .font(.headline)
                        ForEach(document.citations.prefix(8), id: \.self) { citation in
                            HStack(alignment: .top, spacing: 8) {
                                Image(systemName: "quote.opening")
                                    .foregroundStyle(JusticiaTheme.blue)
                                Text(citation)
                                    .font(.caption.monospaced())
                                    .textSelection(.enabled)
                            }
                        }
                    }
                }


                if workspace.analysisDocumentID == document.id,
                   let analysis = workspace.documentAnalysis {
                    Divider()

                    VStack(alignment: .leading, spacing: 14) {
                        HStack {
                            JusticiaIconTile(systemName: "sparkles", color: JusticiaTheme.violet, size: 34)
                            VStack(alignment: .leading, spacing: 2) {
                                Text("ИИ-анализ документа")
                                    .font(.headline)
                                Text(taskTitle(analysis.task) + " · уверенность " + confidenceText(analysis.confidence))
                                    .font(.caption)
                                    .foregroundStyle(JusticiaTheme.secondaryInk)
                            }
                            Spacer()
                        }

                        analysisSection("Общий вывод") {
                            Text(analysis.summary)
                                .font(.subheadline)
                                .lineSpacing(4)
                                .textSelection(.enabled)
                        }

                        if !analysis.issues.isEmpty {
                            analysisSection("Риски и слабые места") {
                                VStack(alignment: .leading, spacing: 9) {
                                    ForEach(analysis.issues) { issue in
                                        HStack(alignment: .top, spacing: 10) {
                                            Circle()
                                                .fill(riskColor(issue.risk))
                                                .frame(width: 8, height: 8)
                                                .padding(.top, 5)
                                            VStack(alignment: .leading, spacing: 3) {
                                                HStack {
                                                    Text(issue.title)
                                                        .font(.subheadline.weight(.semibold))
                                                    JusticiaPill(text: riskTitle(issue.risk), color: riskColor(issue.risk))
                                                }
                                                Text(issue.description)
                                                    .font(.caption)
                                                    .foregroundStyle(JusticiaTheme.secondaryInk)
                                                if let source = issue.sourceText, !source.isEmpty {
                                                    Text(source)
                                                        .font(.caption2)
                                                        .foregroundStyle(JusticiaTheme.secondaryInk)
                                                        .textSelection(.enabled)
                                                }
                                            }
                                            Spacer()
                                        }
                                    }
                                }
                            }
                        }

                        if !analysis.keyFacts.isEmpty {
                            analysisSection("Ключевые факты") {
                                analysisList(analysis.keyFacts, icon: "checkmark.circle", color: JusticiaTheme.green)
                            }
                        }

                        if !analysis.missingInformation.isEmpty {
                            analysisSection("Что требует проверки") {
                                analysisList(analysis.missingInformation, icon: "questionmark.circle", color: JusticiaTheme.orange)
                            }
                        }

                        if !analysis.deadlines.isEmpty {
                            analysisSection("Сроки и даты") {
                                VStack(alignment: .leading, spacing: 8) {
                                    ForEach(Array(analysis.deadlines.enumerated()), id: \.offset) { _, deadline in
                                        HStack(alignment: .top, spacing: 9) {
                                            Image(systemName: "calendar.badge.clock")
                                                .foregroundStyle(JusticiaTheme.orange)
                                            VStack(alignment: .leading, spacing: 2) {
                                                Text(deadline.title)
                                                    .font(.subheadline.weight(.semibold))
                                                Text(deadline.dueDate ?? "Дата требует проверки")
                                                    .font(.caption)
                                                    .foregroundStyle(JusticiaTheme.secondaryInk)
                                                if let source = deadline.sourceText, !source.isEmpty {
                                                    Text(source)
                                                        .font(.caption2)
                                                        .foregroundStyle(JusticiaTheme.secondaryInk)
                                                        .lineLimit(3)
                                                        .textSelection(.enabled)
                                                }
                                            }
                                            Spacer()
                                        }
                                    }
                                }
                            }
                        }

                        Label(
                            "Вывод ИИ — рабочая аналитика. Перед использованием в процессуальном документе проверьте факты, нормы и источники.",
                            systemImage: "checkmark.shield"
                        )
                        .font(.caption)
                        .foregroundStyle(JusticiaTheme.secondaryInk)
                    }
                    .padding(16)
                    .background(JusticiaTheme.surfaceMuted.opacity(0.55))
                    .clipShape(RoundedRectangle(cornerRadius: JusticiaTheme.corner))
                } else if workspace.analyzingDocumentID == document.id {
                    HStack(spacing: 10) {
                        ProgressView()
                        Text("Локальный ИИ анализирует документ…")
                            .font(.subheadline)
                            .foregroundStyle(JusticiaTheme.secondaryInk)
                    }
                    .padding(.vertical, 12)
                }

                if let error = workspace.errorMessage, workspace.analyzingDocumentID == nil {
                    HStack(spacing: 8) {
                        Image(systemName: "exclamationmark.triangle.fill")
                            .foregroundStyle(JusticiaTheme.red)
                        Text(error)
                            .font(.caption)
                            .foregroundStyle(JusticiaTheme.red)
                    }
                }

                Spacer(minLength: 20)
            }
            .frame(maxWidth: .infinity, minHeight: 500, alignment: .topLeading)
            .justiciaCard()
        } else {
            emptyState(
                icon: "doc.text.magnifyingglass",
                title: "Выберите документ",
                message: "Сведения о локально сохранённом документе появятся здесь."
            )
            .frame(maxWidth: .infinity, minHeight: 500)
            .justiciaCard()
        }
    }

    private func metadataRow(_ title: String, _ value: String) -> some View {
        HStack(alignment: .top) {
            Text(title)
                .foregroundStyle(JusticiaTheme.secondaryInk)
                .frame(width: 120, alignment: .leading)
            Text(value)
                .font(.caption.monospaced())
                .textSelection(.enabled)
            Spacer()
        }
    }

    private func byteCount(_ bytes: Int) -> String {
        ByteCountFormatter.string(fromByteCount: Int64(bytes), countStyle: .file)
    }

    @ViewBuilder
    private func analysisSection<Content: View>(
        _ title: String,
        @ViewBuilder content: () -> Content
    ) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title)
                .font(.subheadline.weight(.semibold))
            content()
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private func analysisList(_ items: [String], icon: String, color: Color) -> some View {
        VStack(alignment: .leading, spacing: 7) {
            ForEach(items, id: \.self) { item in
                HStack(alignment: .top, spacing: 8) {
                    Image(systemName: icon)
                        .foregroundStyle(color)
                    Text(item)
                        .font(.caption)
                        .textSelection(.enabled)
                    Spacer()
                }
            }
        }
    }

    private func riskColor(_ risk: String) -> Color {
        switch risk.lowercased() {
        case "critical", "high": JusticiaTheme.red
        case "medium": JusticiaTheme.orange
        case "low": JusticiaTheme.green
        default: JusticiaTheme.secondaryInk
        }
    }

    private func riskTitle(_ risk: String) -> String {
        switch risk.lowercased() {
        case "critical": "Критический"
        case "high": "Высокий"
        case "medium": "Средний"
        case "low": "Низкий"
        default: "Не определён"
        }
    }

    private func taskTitle(_ task: String) -> String {
        switch task {
        case "risk_review": "Анализ рисков"
        case "extract_deadlines": "Извлечение сроков"
        case "summarize": "Резюме"
        default: "Общий анализ"
        }
    }

    private func confidenceText(_ value: Double) -> String {
        String(format: "%.0f%%", value * 100)
    }
}

@ViewBuilder
private func emptyState(icon: String, title: String, message: String) -> some View {
    VStack(spacing: 8) {
        JusticiaIconTile(systemName: icon, color: JusticiaTheme.secondaryInk, size: 40)
        Text(title)
            .font(.subheadline.weight(.semibold))
        Text(message)
            .font(.caption)
            .foregroundStyle(JusticiaTheme.secondaryInk)
            .multilineTextAlignment(.center)
    }
    .frame(maxWidth: .infinity, minHeight: 120)
}
