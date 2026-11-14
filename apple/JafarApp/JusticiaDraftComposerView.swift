import SwiftUI
#if os(macOS)
import UniformTypeIdentifiers
#endif

#if os(macOS)
import AppKit
#endif

struct JusticiaDraftRequestDTO: Codable {
    let kind: String
    let recipient: String
    let author: String
    let position: String
    let legalBasis: String
    let requestedAction: String
    let sourceDocumentIDs: [String]
    let reviewRecordIDs: [String]
    let evidenceGaps: [JusticiaGroundedEvidenceGapDTO]
    let categorizedStatements: [JusticiaGroundedStatementDTO]

    enum CodingKeys: String, CodingKey {
        case kind, recipient, author, position
        case legalBasis = "legal_basis"
        case requestedAction = "requested_action"
        case sourceDocumentIDs = "source_document_ids"
        case reviewRecordIDs = "review_record_ids"
        case evidenceGaps = "evidence_gaps"
        case categorizedStatements = "categorized_statements"
    }

    init(
        kind: String, recipient: String, author: String,
        position: String, legalBasis: String, requestedAction: String,
        sourceDocumentIDs: [String], reviewRecordIDs: [String] = [],
        evidenceGaps: [JusticiaGroundedEvidenceGapDTO] = [],
        categorizedStatements: [JusticiaGroundedStatementDTO] = []
    ) {
        self.kind = kind
        self.recipient = recipient
        self.author = author
        self.position = position
        self.legalBasis = legalBasis
        self.requestedAction = requestedAction
        self.sourceDocumentIDs = sourceDocumentIDs
        self.reviewRecordIDs = reviewRecordIDs
        self.evidenceGaps = evidenceGaps
        self.categorizedStatements = categorizedStatements
    }

    init(from decoder: Decoder) throws {
        let values = try decoder.container(keyedBy: CodingKeys.self)
        kind = try values.decode(String.self, forKey: .kind)
        recipient = try values.decode(String.self, forKey: .recipient)
        author = try values.decode(String.self, forKey: .author)
        position = try values.decode(String.self, forKey: .position)
        legalBasis = try values.decode(String.self, forKey: .legalBasis)
        requestedAction = try values.decode(String.self, forKey: .requestedAction)
        sourceDocumentIDs = try values.decode([String].self, forKey: .sourceDocumentIDs)
        // Old encrypted drafts did not contain these fields.
        reviewRecordIDs = try values.decodeIfPresent([String].self, forKey: .reviewRecordIDs) ?? []
        evidenceGaps = try values.decodeIfPresent([JusticiaGroundedEvidenceGapDTO].self, forKey: .evidenceGaps) ?? []
        categorizedStatements = try values.decodeIfPresent([JusticiaGroundedStatementDTO].self, forKey: .categorizedStatements) ?? []
    }
}

struct JusticiaDraftEvidenceDTO: Decodable, Identifiable {
    let documentID: String
    let filename: String
    let chunkIndex: Int
    let citation: String
    let excerpt: String

    var id: String { documentID + ":" + String(chunkIndex) }

    enum CodingKeys: String, CodingKey {
        case documentID = "document_id"
        case filename
        case chunkIndex = "chunk_index"
        case citation, excerpt
    }
}

struct JusticiaDraftPreviewDTO: Decodable {
    let title: String
    let warnings: [String]
    let evidence: [JusticiaDraftEvidenceDTO]
    let evidenceGaps: [JusticiaGroundedEvidenceGapDTO]
    let categorizedStatements: [JusticiaGroundedStatementDTO]
    let canExport: Bool

    enum CodingKeys: String, CodingKey {
        case title, warnings, evidence
        case evidenceGaps = "evidence_gaps"
        case categorizedStatements = "categorized_statements"
        case canExport = "can_export"
    }

    init(from decoder: Decoder) throws {
        let values = try decoder.container(keyedBy: CodingKeys.self)
        title = try values.decode(String.self, forKey: .title)
        warnings = try values.decode([String].self, forKey: .warnings)
        evidence = try values.decode([JusticiaDraftEvidenceDTO].self, forKey: .evidence)
        evidenceGaps = try values.decodeIfPresent([JusticiaGroundedEvidenceGapDTO].self, forKey: .evidenceGaps) ?? []
        categorizedStatements = try values.decodeIfPresent([JusticiaGroundedStatementDTO].self, forKey: .categorizedStatements) ?? []
        canExport = try values.decode(Bool.self, forKey: .canExport)
    }
}

struct JusticiaDraftSuggestionDTO: Decodable {
    let proposedPosition: String
    let citations: [String]
    let pointsToVerify: [String]
    let localOnly: Bool

    enum CodingKeys: String, CodingKey {
        case proposedPosition = "proposed_position"
        case citations
        case pointsToVerify = "points_to_verify"
        case localOnly = "local_only"
    }
}

/// Working draft: user-entered facts and legal grounds, source-verified excerpts.
/// No model-generated allegations or unverifiable case-file page references.
struct JusticiaDraftComposerView: View {
    @ObservedObject var workspace: JusticiaWorkspaceStore
    let apiClient: JusticiaAPIClient?

    @State private var kind = "motion"
    @State private var recipient = ""
    @State private var author = ""
    @State private var position = ""
    @State private var legalBasis = ""
    @State private var requestedAction = ""
    @State private var selectedDocIDs: Set<String> = []
    @State private var selectedReviewIDs: Set<String> = []
    @State private var reviewerDecisions: [JusticiaClaimDecisionRecordDTO] = []
    @State private var preview: JusticiaDraftPreviewDTO?
    @State private var aiSuggestion: JusticiaDraftSuggestionDTO?
    @State private var isProcessing = false
    @State private var message: String?
    @State private var errorMessage: String?

    private let types: [(String, String)] = [
        ("motion", "Ходатайство"),
        ("complaint", "Жалоба"),
        ("objections", "Возражения"),
        ("appeal", "Апелляционная жалоба"),
        ("statement", "Заявление")
    ]

    private var inputSignature: String {
        [
            workspace.selectedMatterID ?? "",
            kind, recipient, author, position, legalBasis, requestedAction,
            selectedDocIDs.sorted().joined(separator: ","),
            selectedReviewIDs.sorted().joined(separator: ",")
        ].joined(separator: "\u{001F}")
    }

    private var draft: JusticiaDraftRequestDTO {
        JusticiaDraftRequestDTO(
            kind: kind,
            recipient: recipient,
            author: author,
            position: position,
            legalBasis: legalBasis,
            requestedAction: requestedAction,
            sourceDocumentIDs: selectedDocIDs.sorted(),
            reviewRecordIDs: selectedReviewIDs.sorted()
        )
    }

    private var latestWorkingDecisions: [JusticiaClaimDecisionRecordDTO] {
        var seen = Set<String>()
        return reviewerDecisions.filter { entry in
            guard seen.insert(entry.candidateID).inserted else { return false }
            return entry.decision == "keep_for_work"
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                Image(systemName: "doc.badge.plus")
                    .foregroundStyle(JusticiaTheme.blue)
                Text("Подготовка процессуального документа")
                    .font(.title3.weight(.semibold))
                    .foregroundStyle(JusticiaTheme.ink)
            }
            Text("Рабочий проект составляется из введённой вами позиции и подтверждённых локальных материалов выбранного дела. Нормы права и реквизиты автоматически не выдумываются.")
                .font(.subheadline)
                .foregroundStyle(JusticiaTheme.secondaryInk)

            if let matter = workspace.selectedMatter, apiClient != nil {
                Text("Дело: " + matter.title)
                    .font(.subheadline.weight(.medium))

                JusticiaDraftHistoryPanel(
                    matterID: workspace.selectedMatterID,
                    apiClient: apiClient,
                    draft: draft,
                    inputSignature: inputSignature,
                    onLoad: { stored in
                        kind = stored.kind
                        recipient = stored.recipient
                        author = stored.author
                        position = stored.position
                        legalBasis = stored.legalBasis
                        requestedAction = stored.requestedAction
                        selectedDocIDs = Set(stored.sourceDocumentIDs)
                        selectedReviewIDs = Set(stored.reviewRecordIDs)
                        preview = nil
                        aiSuggestion = nil
                    }
                )

                Picker("Вид документа", selection: $kind) {
                    ForEach(types.indices, id: \.self) { index in
                        Text(types[index].1).tag(types[index].0)
                    }
                }

                TextField("Адресат (суд, следователь, орган)", text: $recipient)
                    .textFieldStyle(.roundedBorder)
                TextField("Заявитель и процессуальное положение", text: $author)
                    .textFieldStyle(.roundedBorder)

                editor("Изложение обстоятельств и позиции", text: $position, height: 125)
                editor("Правовые основания, проверенные юристом", text: $legalBasis, height: 85)
                editor("Просительная часть", text: $requestedAction, height: 85)

                VStack(alignment: .leading, spacing: 8) {
                    Text("Материалы дела для проверки")
                        .font(.subheadline.weight(.semibold))
                    if workspace.documents.isEmpty {
                        Text("Сначала импортируйте документы в раздел «Документы».")
                            .foregroundStyle(JusticiaTheme.secondaryInk)
                    } else {
                        ForEach(workspace.documents) { document in
                            Toggle(
                                document.filename,
                                isOn: Binding(
                                    get: { selectedDocIDs.contains(document.id) },
                                    set: { enabled in
                                        if enabled {
                                            selectedDocIDs.insert(document.id)
                                        } else {
                                            selectedDocIDs.remove(document.id)
                                        }
                                    }
                                )
                            )
                            .disabled(document.state != "READY" && document.state != "ready")
                        }
                    }
                }

                VStack(alignment: .leading, spacing: 8) {
                    Text("Рабочие замечания из журнала проверок")
                        .font(.subheadline.weight(.semibold))
                    Text("Они попадут только в служебный лист Word после разрыва страницы. "
                         + "Не заменяют изложение позиции и не считаются установленными фактами.")
                        .font(.caption)
                        .foregroundStyle(JusticiaTheme.secondaryInk)
                    if latestWorkingDecisions.isEmpty {
                        Text("Нет подходящих текущих решений «Оставить для работы».")
                            .font(.caption)
                            .foregroundStyle(JusticiaTheme.secondaryInk)
                    } else {
                        ForEach(latestWorkingDecisions) { entry in
                            Toggle(
                                entry.note,
                                isOn: Binding(
                                    get: { selectedReviewIDs.contains(entry.recordID) },
                                    set: { checked in
                                        if checked { selectedReviewIDs.insert(entry.recordID) }
                                        else { selectedReviewIDs.remove(entry.recordID) }
                                    }
                                )
                            )
                            .disabled(
                                !selectedDocIDs.contains(entry.left.documentID) ||
                                !selectedDocIDs.contains(entry.right.documentID)
                            )
                        }
                    }
                    if !selectedReviewIDs.isEmpty {
                        Button("Сбросить выбранные замечания") {
                            selectedReviewIDs.removeAll()
                        }
                        .buttonStyle(.borderless)
                    }
                }

                HStack(spacing: 12) {
                    Button {
                        Task { await runPreview() }
                    } label: {
                        Label("Проверить проект", systemImage: "checkmark.shield")
                    }
                    .disabled(isProcessing)

                    Button {
                        Task { await suggestPosition() }
                    } label: {
                        Label("Предложить текст локальным ИИ", systemImage: "sparkles")
                    }
                    .disabled(
                        isProcessing || selectedDocIDs.isEmpty ||
                        (position.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty &&
                         requestedAction.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                    )

                    Button {
                        Task { await exportWord() }
                    } label: {
                        Label("Сохранить Word", systemImage: "square.and.arrow.down")
                    }
                    .disabled(isProcessing || !(preview?.canExport ?? false))
                }
                .buttonStyle(.bordered)
                .controlSize(.regular)

                if isProcessing {
                    ProgressView("Проверяем источники…")
                }
                if let errorMessage {
                    Text(errorMessage)
                        .foregroundStyle(JusticiaTheme.red)
                        .font(.subheadline)
                }
                if let message {
                    Text(message)
                        .foregroundStyle(JusticiaTheme.green)
                        .font(.subheadline)
                }
                if let preview {
                    previewSection(preview)
                }
                if let suggestion = aiSuggestion {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Предложение локального ИИ — требует проверки")
                            .font(.headline)
                        Text(suggestion.proposedPosition)
                            .font(.body)
                            .textSelection(.enabled)
                        ForEach(suggestion.pointsToVerify, id: \.self) { point in
                            Label(point, systemImage: "exclamationmark.triangle")
                                .font(.caption)
                        }
                        Text("Ссылок на выбранные фрагменты: \(suggestion.citations.count)")
                            .font(.caption)
                        Button("Вставить предложенную позицию для редактирования") {
                            position = suggestion.proposedPosition
                            self.aiSuggestion = nil
                            preview = nil
                        }
                        .buttonStyle(.bordered)
                    }
                    .padding(.top, 12)
                }
            } else {
                Text("Выберите дело и запустите локальный сервис «Юстиции».")
                    .font(.subheadline)
                    .foregroundStyle(JusticiaTheme.secondaryInk)
            }
        }
        .padding(18)
        .justiciaCard()
        .onChange(of: inputSignature) { _, _ in
            preview = nil
            aiSuggestion = nil
            message = nil
        }
        .task(id: workspace.selectedMatterID) {
            await loadReviewerDecisions()
        }
        .onChange(of: workspace.selectedMatterID) { _, _ in
            reviewerDecisions = []
            selectedReviewIDs = []
            kind = "motion"
            recipient = ""
            author = ""
            position = ""
            legalBasis = ""
            requestedAction = ""
            selectedDocIDs = []
            preview = nil
            aiSuggestion = nil
            errorMessage = nil
            message = nil
        }
    }

    private func editor(_ label: String, text: Binding<String>, height: CGFloat) -> some View {
        VStack(alignment: .leading, spacing: 5) {
            Text(label).font(.subheadline.weight(.medium))
            TextEditor(text: text)
                .font(.body)
                .frame(minHeight: height)
                .padding(5)
                .overlay(
                    RoundedRectangle(cornerRadius: 8)
                        .stroke(JusticiaTheme.border, lineWidth: 1)
                )
        }
    }

    private func previewSection(_ result: JusticiaDraftPreviewDTO) -> some View {
        VStack(alignment: .leading, spacing: 9) {
            Text(result.title).font(.headline)
            Text("Проверенных фрагментов: \(result.evidence.count)")
                .font(.subheadline)
            ForEach(result.evidence) { evidence in
                VStack(alignment: .leading, spacing: 3) {
                    Text(evidence.filename + " · фрагмент " + String(evidence.chunkIndex + 1))
                        .font(.caption.weight(.semibold))
                    Text(evidence.excerpt)
                        .font(.caption)
                        .foregroundStyle(JusticiaTheme.secondaryInk)
                        .textSelection(.enabled)
                }
            }
            ForEach(result.warnings, id: \.self) { warning in
                Label(warning, systemImage: "exclamationmark.triangle")
                    .font(.caption)
                    .foregroundStyle(JusticiaTheme.secondaryInk)
            }
            Text(result.canExport
                 ? "Экспорт доступен. Перед подачей проверьте документ и первоисточники."
                 : "Заполните обязательные поля и выберите индексированный документ.")
                .font(.subheadline)
                .foregroundStyle(result.canExport ? JusticiaTheme.green : JusticiaTheme.orange)
        }
        .padding(.top, 8)
    }

    @MainActor
    private func loadReviewerDecisions() async {
        guard let apiClient, let matterID = workspace.selectedMatterID else { return }
        do {
            let records = try await apiClient.listClaimReviewDecisions(matterID: matterID)
            guard workspace.selectedMatterID == matterID else { return }
            reviewerDecisions = records
        } catch {
            // Draft editing remains available even without a review register.
            if workspace.selectedMatterID == matterID {
                reviewerDecisions = []
            }
        }
    }

    @MainActor
    private func runPreview() async {
        guard let apiClient, let matterID = workspace.selectedMatterID else { return }
        isProcessing = true
        preview = nil
        errorMessage = nil
        defer { isProcessing = false }
        do {
            preview = try await apiClient.previewDraft(matterID: matterID, draft: draft)
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    @MainActor
    private func suggestPosition() async {
        guard let apiClient, let matterID = workspace.selectedMatterID else { return }
        let signature = inputSignature
        isProcessing = true
        aiSuggestion = nil
        errorMessage = nil
        defer { isProcessing = false }
        do {
            let suggestion = try await apiClient.suggestDraft(matterID: matterID, draft: draft)
            if signature == inputSignature {
                aiSuggestion = suggestion
            }
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    @MainActor
    private func exportWord() async {
        guard let apiClient,
              let matterID = workspace.selectedMatterID,
              preview?.canExport == true else { return }
        isProcessing = true
        errorMessage = nil
        defer { isProcessing = false }
        do {
            let data = try await apiClient.exportDraft(matterID: matterID, draft: draft)
            #if os(macOS)
            let panel = NSSavePanel()
            panel.nameFieldStringValue = "Проект процессуального документа.docx"
            panel.allowedContentTypes = [.init(filenameExtension: "docx")!]
            if panel.runModal() == .OK, let url = panel.url {
                try data.write(to: url, options: .atomic)
                message = "Word сохранён. Документ требует проверки и подписания."
            }
            #else
            _ = data
            errorMessage = "Сохранение DOCX в этой бета-версии доступно на macOS."
            #endif
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}
