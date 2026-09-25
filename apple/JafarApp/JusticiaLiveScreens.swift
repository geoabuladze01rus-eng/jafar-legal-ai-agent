import SwiftUI
import UniformTypeIdentifiers

struct JusticiaLiveHomeView: View {
    @ObservedObject var workspace: JusticiaWorkspaceStore
    let navigate: (JusticiaSection) -> Void

    private let columns = [GridItem(.adaptive(minimum: 210), spacing: 14)]

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            pageHeader(
                title: "Добро пожаловать в «Юстицию»",
                subtitle: "Локальная рабочая среда для дел, документов, сроков и юридического ИИ."
            )

            if workspace.isLoading {
                ProgressView("Загружаем локальные данные…")
                    .frame(maxWidth: .infinity, minHeight: 80)
                    .justiciaCard()
            } else if let error = workspace.errorMessage {
                errorCard(error)
            }

            LazyVGrid(columns: columns, spacing: 14) {
                metricCard("Активные дела", "\(activeMatters)", "из \(workspace.matters.count) дел", "briefcase", JusticiaTheme.blue)
                metricCard("Ближайшие сроки", "\(deadlineCount)", "в локальной базе", "calendar.badge.exclamationmark", JusticiaTheme.orange)
                metricCard("Документы дела", "\(workspace.documents.count)", workspace.selectedMatter == nil ? "выберите дело" : "по выбранному делу", "doc.text", JusticiaTheme.blue)
                metricCard("Режим данных", "Локально", "защищённое хранилище", "lock.shield", JusticiaTheme.green)
            }

            HStack(alignment: .top, spacing: 14) {
                VStack(alignment: .leading, spacing: 12) {
                    sectionTitle("Последние дела", action: "Все дела") { navigate(.matters) }

                    if workspace.matters.isEmpty {
                        emptyState(
                            icon: "briefcase",
                            title: "Дел пока нет",
                            message: "Создайте первое дело — оно сохранится в локальном зашифрованном хранилище."
                        )
                    } else {
                        ForEach(workspace.matters.prefix(5)) { matter in
                            Button {
                                Task {
                                    await workspace.selectMatter(matter)
                                    navigate(.matters)
                                }
                            } label: {
                                HStack(spacing: 12) {
                                    JusticiaIconTile(systemName: "briefcase", color: JusticiaTheme.blue, size: 34)
                                    VStack(alignment: .leading, spacing: 3) {
                                        Text(matter.displayNumber)
                                            .font(.subheadline.weight(.semibold))
                                            .foregroundStyle(JusticiaTheme.ink)
                                        Text(matter.title)
                                            .font(.caption)
                                            .foregroundStyle(JusticiaTheme.secondaryInk)
                                            .lineLimit(1)
                                    }
                                    Spacer()
                                    JusticiaPill(text: matter.displayStatus, color: JusticiaTheme.green)
                                }
                                .padding(.vertical, 5)
                            }
                            .buttonStyle(.plain)
                        }
                    }
                }
                .justiciaCard()
                .frame(maxWidth: .infinity)

                VStack(alignment: .leading, spacing: 12) {
                    sectionTitle("Ближайшие сроки", action: "Открыть сроки") { navigate(.deadlines) }

                    let upcoming = workspace.matters.flatMap { matter in
                        matter.deadlines.map { (matter, $0) }
                    }.prefix(5)

                    if upcoming.isEmpty {
                        emptyState(
                            icon: "calendar",
                            title: "Сроки не добавлены",
                            message: "Сроки из материалов дела будут появляться здесь после обработки документов."
                        )
                    } else {
                        ForEach(Array(upcoming.enumerated()), id: \.offset) { _, pair in
                            HStack(spacing: 12) {
                                JusticiaIconTile(systemName: "calendar.badge.clock", color: JusticiaTheme.orange, size: 34)
                                VStack(alignment: .leading, spacing: 3) {
                                    Text(pair.1.title)
                                        .font(.subheadline.weight(.semibold))
                                    Text(pair.0.displayNumber + (pair.1.dueDate.map { " · " + $0 } ?? ""))
                                        .font(.caption)
                                        .foregroundStyle(JusticiaTheme.secondaryInk)
                                }
                                Spacer()
                            }
                        }
                    }
                }
                .justiciaCard()
                .frame(maxWidth: .infinity)
            }

            HStack(spacing: 12) {
                quickButton("Открыть дела", "briefcase.fill", .matters)
                quickButton("Документы", "doc.text.magnifyingglass", .documents)
                quickButton("Транскрибация", "waveform", .transcription)
            }
        }
        .task {
            if workspace.matters.isEmpty {
                await workspace.refresh()
            }
        }
    }

    private var activeMatters: Int {
        workspace.matters.filter { $0.status.lowercased() == "active" }.count
    }

    private var deadlineCount: Int {
        workspace.matters.reduce(0) { $0 + $1.deadlines.count }
    }

    private func metricCard(_ title: String, _ value: String, _ note: String, _ icon: String, _ color: Color) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                JusticiaIconTile(systemName: icon, color: color)
                Spacer()
            }
            Text(value)
                .font(.system(size: 28, weight: .bold, design: .rounded))
                .foregroundStyle(JusticiaTheme.ink)
            Text(title)
                .font(.subheadline.weight(.semibold))
            Text(note)
                .font(.caption)
                .foregroundStyle(JusticiaTheme.secondaryInk)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .justiciaCard()
    }

    private func quickButton(_ title: String, _ icon: String, _ section: JusticiaSection) -> some View {
        Button {
            navigate(section)
        } label: {
            Label(title, systemImage: icon)
                .font(.subheadline.weight(.semibold))
                .frame(maxWidth: .infinity)
                .padding(.vertical, 11)
        }
        .buttonStyle(.bordered)
    }

    private func errorCard(_ error: String) -> some View {
        HStack(spacing: 10) {
            Image(systemName: "exclamationmark.triangle.fill")
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
    @State private var filter = ""
    @State private var showingCreateMatter = false

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
                        Button {
                            showingCreateMatter = true
                        } label: {
                            Label("Новое дело", systemImage: "plus")
                        }
                        .buttonStyle(.borderedProminent)
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
        .sheet(isPresented: $showingCreateMatter) {
            JusticiaCreateMatterSheet(workspace: workspace)
                .frame(minWidth: 520, minHeight: 560)
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

private struct JusticiaCreateMatterSheet: View {
    @Environment(\.dismiss) private var dismiss
    @ObservedObject var workspace: JusticiaWorkspaceStore

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
                        if saved { dismiss() }
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
    @State private var selectedDocumentID: String?

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
                                selectedDocumentID = document.id
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
                                .background(selectedDocumentID == document.id ? JusticiaTheme.blueSoft : Color.clear)
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
            if selectedDocumentID == nil {
                selectedDocumentID = workspace.documents.first?.id
            }
        }
        .fileImporter(isPresented: $showingImporter, allowedContentTypes: allowedTypes, allowsMultipleSelection: false) { result in
            if case .success(let urls) = result, let url = urls.first {
                Task {
                    let imported = await workspace.importDocument(from: url)
                    if imported {
                        selectedDocumentID = workspace.documents.first?.id
                    }
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
        if let document = workspace.documents.first(where: { $0.id == selectedDocumentID }) ?? workspace.documents.first {
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
