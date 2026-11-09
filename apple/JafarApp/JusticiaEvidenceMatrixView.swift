import SwiftUI

#if os(macOS)
import AppKit
import UniformTypeIdentifiers
#endif

struct JusticiaMatrixRequestDTO: Encodable {
    let sourceDocumentIDs: [String]
    let comparisonSubject: String

    enum CodingKeys: String, CodingKey {
        case sourceDocumentIDs = "source_document_ids"
        case comparisonSubject = "comparison_subject"
    }
}

struct JusticiaMatrixSourceDTO: Decodable, Identifiable {
    let documentID: String
    let filename: String
    let chunkCount: Int

    var id: String { documentID }

    enum CodingKeys: String, CodingKey {
        case documentID = "document_id"
        case filename
        case chunkCount = "chunk_count"
    }
}

struct JusticiaMatrixEvidenceDTO: Decodable, Identifiable {
    let key: String
    let label: String
    let value: String
    let documentID: String
    let filename: String
    let citation: String
    let excerpt: String

    var id: String { documentID + citation + key + value }

    enum CodingKeys: String, CodingKey {
        case key, label, value
        case documentID = "document_id"
        case filename, citation, excerpt
    }
}

struct JusticiaMatrixComparisonDTO: Decodable, Identifiable {
    let key: String
    let label: String
    let status: String
    let interpretations: [String]
    let evidence: [JusticiaMatrixEvidenceDTO]

    var id: String { key }
}

struct JusticiaMatrixResponseDTO: Decodable {
    let matterID: String
    let matterTitle: String
    let comparisonSubject: String
    let sources: [JusticiaMatrixSourceDTO]
    let comparisons: [JusticiaMatrixComparisonDTO]
    let otherValues: [JusticiaMatrixEvidenceDTO]
    let possibleDifferenceCount: Int
    let warnings: [String]

    enum CodingKeys: String, CodingKey {
        case matterID = "matter_id"
        case matterTitle = "matter_title"
        case comparisonSubject = "comparison_subject"
        case sources, comparisons
        case otherValues = "other_values"
        case possibleDifferenceCount = "possible_difference_count"
        case warnings
    }
}

/// Explicit local comparison of selected Matter documents; no remote AI calls.
struct JusticiaEvidenceMatrixView: View {
    @ObservedObject var workspace: JusticiaWorkspaceStore
    let apiClient: JusticiaAPIClient?

    @State private var selectedIDs: Set<String> = []
    @State private var subject = ""
    @State private var report: JusticiaMatrixResponseDTO?
    @State private var errorText: String?
    @State private var statusText: String?
    @State private var isRunning = false

    private var signature: String {
        [
            workspace.selectedMatterID ?? "",
            subject,
            selectedIDs.sorted().joined(separator: ",")
        ].joined(separator: "\u{001F}")
    }

    private var payload: JusticiaMatrixRequestDTO {
        JusticiaMatrixRequestDTO(
            sourceDocumentIDs: selectedIDs.sorted(),
            comparisonSubject: subject
        )
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            Label("Сопоставление материалов дела", systemImage: "doc.text.magnifyingglass")
                .font(.title3.weight(.semibold))
                .foregroundStyle(JusticiaTheme.ink)

            Text("Проверка явно указанных дат и денежных сумм в нескольких документах. Разные значения рассматриваются как повод для сверки, а не как установленное противоречие.")
                .font(.subheadline)
                .foregroundStyle(JusticiaTheme.secondaryInk)

            if let matter = workspace.selectedMatter, apiClient != nil {
                Text("Выбрано дело: " + matter.title)
                    .font(.subheadline.weight(.medium))

                TextField("Предмет сравнения (например, один договор)", text: $subject)
                    .textFieldStyle(.roundedBorder)

                if workspace.documents.count < 2 {
                    Text("Для сопоставления импортируйте в дело хотя бы два документа.")
                        .foregroundStyle(JusticiaTheme.secondaryInk)
                } else {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Выберите от 2 до 12 документов").font(.subheadline.weight(.medium))
                        ForEach(workspace.documents) { document in
                            Toggle(
                                document.filename,
                                isOn: Binding(
                                    get: { selectedIDs.contains(document.id) },
                                    set: { enabled in
                                        if enabled { selectedIDs.insert(document.id) }
                                        else { selectedIDs.remove(document.id) }
                                    }
                                )
                            )
                            .disabled(document.state.uppercased() != "READY")
                        }
                    }

                    HStack(spacing: 10) {
                        Button {
                            Task { await compare() }
                        } label: {
                            Label("Сопоставить", systemImage: "checkmark.shield")
                        }
                        .disabled(isRunning || selectedIDs.count < 2 || selectedIDs.count > 12)

                        Button {
                            Task { await exportWord() }
                        } label: {
                            Label("Сохранить справку Word", systemImage: "square.and.arrow.down")
                        }
                        .disabled(isRunning || report == nil)
                    }
                    .buttonStyle(.bordered)
                }

                if isRunning { ProgressView("Сверяем локальные материалы…") }
                if let errorText {
                    Text(errorText)
                        .font(.subheadline)
                        .foregroundStyle(JusticiaTheme.red)
                }
                if let statusText {
                    Text(statusText)
                        .font(.subheadline)
                        .foregroundStyle(JusticiaTheme.green)
                }
                if let report {
                    reportBody(report)
                }
            } else {
                Text("Выберите дело и запустите локальный сервис «Юстиции».")
                    .foregroundStyle(JusticiaTheme.secondaryInk)
            }
        }
        .padding(18)
        .justiciaCard()
        .onChange(of: signature) { _, _ in
            report = nil
            statusText = nil
        }
        .onChange(of: workspace.selectedMatterID) { _, _ in
            selectedIDs.removeAll()
            subject = ""
            report = nil
            errorText = nil
            statusText = nil
        }
    }

    @ViewBuilder
    private func reportBody(_ data: JusticiaMatrixResponseDTO) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Служебная проверочная справка")
                .font(.headline)
            Text("Потенциальных различий: \(data.possibleDifferenceCount)")
                .font(.subheadline.weight(.medium))

            if data.comparisons.isEmpty {
                Text("Сопоставимых явно подписанных полей не найдено. Это не означает, что документы согласованы.")
                    .font(.subheadline)
                    .foregroundStyle(JusticiaTheme.secondaryInk)
            }

            ForEach(data.comparisons) { comparison in
                VStack(alignment: .leading, spacing: 7) {
                    HStack {
                        Text(comparison.label)
                            .font(.subheadline.weight(.semibold))
                        Spacer()
                        Text(statusTitle(comparison.status))
                            .font(.caption.weight(.medium))
                            .foregroundStyle(
                                comparison.status == "same_labelled_value"
                                ? JusticiaTheme.green : JusticiaTheme.orange
                            )
                    }
                    ForEach(comparison.evidence) { item in
                        evidenceRow(item)
                    }
                    ForEach(comparison.interpretations, id: \.self) { note in
                        Text(note)
                            .font(.caption)
                            .foregroundStyle(JusticiaTheme.secondaryInk)
                    }
                }
                .padding(12)
                .background(JusticiaTheme.surfaceMuted)
                .clipShape(RoundedRectangle(cornerRadius: 10))
            }

            if !data.otherValues.isEmpty {
                Text("Значения без достаточной пары для сравнения")
                    .font(.subheadline.weight(.semibold))
                ForEach(data.otherValues) { item in
                    evidenceRow(item)
                }
            }

            ForEach(data.warnings, id: \.self) { warning in
                Label(warning, systemImage: "exclamationmark.triangle")
                    .font(.caption)
                    .foregroundStyle(JusticiaTheme.secondaryInk)
            }
        }
        .padding(.top, 8)
    }

    private func evidenceRow(_ item: JusticiaMatrixEvidenceDTO) -> some View {
        VStack(alignment: .leading, spacing: 3) {
            Text(item.filename + ": " + item.value)
                .font(.caption.weight(.semibold))
            Text(item.excerpt)
                .font(.caption)
                .foregroundStyle(JusticiaTheme.secondaryInk)
                .textSelection(.enabled)
            Text("Технический источник: " + item.citation)
                .font(.caption2)
                .foregroundStyle(JusticiaTheme.secondaryInk)
                .textSelection(.enabled)
        }
    }

    private func statusTitle(_ status: String) -> String {
        switch status {
        case "possible_difference": return "Требует сверки"
        case "ambiguous_within_document": return "Несколько значений"
        case "same_labelled_value": return "Значения совпадают"
        default: return "Результат требует проверки"
        }
    }

    @MainActor
    private func compare() async {
        guard let apiClient, let matterID = workspace.selectedMatterID,
              (2...12).contains(selectedIDs.count) else { return }
        let currentSignature = signature
        let request = payload
        isRunning = true
        report = nil
        errorText = nil
        defer { isRunning = false }
        do {
            let result = try await apiClient.compareEvidence(matterID: matterID, request: request)
            if signature == currentSignature && result.matterID == matterID {
                report = result
            }
        } catch {
            if signature == currentSignature {
                errorText = error.localizedDescription
            }
        }
    }

    @MainActor
    private func exportWord() async {
        guard let apiClient, let matterID = workspace.selectedMatterID,
              let report, report.matterID == matterID,
              (2...12).contains(selectedIDs.count) else { return }
        let currentSignature = signature
        let request = payload
        isRunning = true
        errorText = nil
        defer { isRunning = false }
        do {
            let data = try await apiClient.exportEvidenceMatrix(matterID: matterID, request: request)
            guard signature == currentSignature else { return }
            #if os(macOS)
            let panel = NSSavePanel()
            panel.nameFieldStringValue = "Сопоставление документов.docx"
            panel.allowedContentTypes = [UTType(filenameExtension: "docx")!]
            if panel.runModal() == .OK, let url = panel.url {
                try data.write(to: url, options: .atomic)
                statusText = "Проверочная справка сохранена. Проверьте первоисточники."
            }
            #else
            _ = data
            errorText = "В этой бета-версии экспорт DOCX доступен на macOS."
            #endif
        } catch {
            if signature == currentSignature {
                errorText = error.localizedDescription
            }
        }
    }
}
