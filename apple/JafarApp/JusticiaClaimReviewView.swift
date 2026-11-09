import SwiftUI

#if os(macOS)
import AppKit
import UniformTypeIdentifiers
#endif

struct JusticiaClaimReviewRequestDTO: Encodable {
    let sourceDocumentIDs: [String]
    let focus: String

    enum CodingKeys: String, CodingKey {
        case sourceDocumentIDs = "source_document_ids"
        case focus
    }
}

struct JusticiaGroundedClaimDTO: Codable, Identifiable {
    let citation: String
    let quote: String
    let subject: String
    let eventAnchor: String
    let actionKey: String
    let polarity: String
    let documentID: String
    let filename: String
    let physicalPage: Int?

    var id: String {
        citation + ":" + quote + ":" + polarity
    }

    enum CodingKeys: String, CodingKey {
        case citation, quote, subject
        case eventAnchor = "event_anchor"
        case actionKey = "action_key"
        case polarity
        case documentID = "document_id"
        case filename
        case physicalPage = "physical_page"
    }
}

struct JusticiaCandidateDifferenceDTO: Codable, Identifiable {
    let id: String
    let left: JusticiaGroundedClaimDTO
    let right: JusticiaGroundedClaimDTO
    let status: String
    let reason: String
}

struct JusticiaClaimReviewReportDTO: Codable {
    let matterID: String
    let matterTitle: String
    let focus: String
    let sourceDocumentIDs: [String]
    let claims: [JusticiaGroundedClaimDTO]
    let possibleDifferences: [JusticiaCandidateDifferenceDTO]
    let warnings: [String]

    enum CodingKeys: String, CodingKey {
        case matterID = "matter_id"
        case matterTitle = "matter_title"
        case focus
        case sourceDocumentIDs = "source_document_ids"
        case claims
        case possibleDifferences = "possible_differences"
        case warnings
    }
}

/// Source-checking is enforced on the local server. A matching source does
/// not turn a model statement into a factual or procedural finding.
struct JusticiaClaimReviewView: View {
    @ObservedObject var workspace: JusticiaWorkspaceStore
    let apiClient: JusticiaAPIClient?

    @State private var focus = ""
    @State private var selectedIDs: Set<String> = []
    @State private var report: JusticiaClaimReviewReportDTO?
    @State private var isWorking = false
    @State private var errorText: String?
    @State private var successText: String?

    private var signature: String {
        [
            workspace.selectedMatterID ?? "",
            focus,
            selectedIDs.sorted().joined(separator: ",")
        ].joined(separator: "\u{001F}")
    }

    private var request: JusticiaClaimReviewRequestDTO {
        JusticiaClaimReviewRequestDTO(
            sourceDocumentIDs: selectedIDs.sorted(),
            focus: focus.trimmingCharacters(in: .whitespacesAndNewlines)
        )
    }

    private var canInspect: Bool {
        !isWorking && (2...8).contains(selectedIDs.count)
        && (5...400).contains(focus.trimmingCharacters(in: .whitespacesAndNewlines).count)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            Label("Расхождения в обстоятельствах", systemImage: "text.book.closed")
                .font(.title3.weight(.semibold))
                .foregroundStyle(JusticiaTheme.ink)
            Text("Локальная модель предлагает для проверки дословные высказывания, относящиеся к одному предполагаемому эпизоду. Это гипотезы, а не установленные противоречия.")
                .font(.subheadline)
                .foregroundStyle(JusticiaTheme.secondaryInk)

            if let matter = workspace.selectedMatter, apiClient != nil {
                Text("Дело: " + matter.title)
                    .font(.subheadline.weight(.medium))
                TextField("Какой эпизод или факт нужно сверить?", text: $focus)
                    .textFieldStyle(.roundedBorder)
                Text("Укажите конкретное событие, участника, номер договора или период.")
                    .font(.caption)
                    .foregroundStyle(JusticiaTheme.secondaryInk)

                VStack(alignment: .leading, spacing: 6) {
                    Text("Выберите от 2 до 8 документов")
                        .font(.subheadline.weight(.semibold))
                    ForEach(workspace.documents) { document in
                        Toggle(
                            document.filename,
                            isOn: Binding(
                                get: { selectedIDs.contains(document.id) },
                                set: { checked in
                                    if checked { selectedIDs.insert(document.id) }
                                    else { selectedIDs.remove(document.id) }
                                }
                            )
                        )
                        .disabled(document.state.uppercased() != "READY")
                    }
                }

                HStack(spacing: 10) {
                    Button {
                        Task { await inspect() }
                    } label: {
                        Label("Проверить высказывания локальным ИИ", systemImage: "checkmark.shield")
                    }
                    .disabled(!canInspect)

                    Button {
                        Task { await exportWord() }
                    } label: {
                        Label("Сохранить проверочную справку Word", systemImage: "square.and.arrow.down")
                    }
                    .disabled(isWorking || report == nil)
                }
                .buttonStyle(.bordered)

                if isWorking { ProgressView("Проверяем дословные выдержки…") }
                if let errorText {
                    Text(errorText).foregroundStyle(JusticiaTheme.red)
                        .font(.subheadline)
                }
                if let successText {
                    Text(successText).foregroundStyle(JusticiaTheme.green)
                        .font(.subheadline)
                }
                if let report {
                    reviewBody(report)
                }
            } else {
                Text("Выберите дело и запустите локальную «Юстицию».")
                    .foregroundStyle(JusticiaTheme.secondaryInk)
            }
        }
        .padding(18)
        .justiciaCard()
        .onChange(of: signature) { _, _ in
            report = nil
            successText = nil
        }
        .onChange(of: workspace.selectedMatterID) { _, _ in
            selectedIDs.removeAll()
            focus = ""
            report = nil
            errorText = nil
            successText = nil
        }
    }

    @ViewBuilder
    private func reviewBody(_ value: JusticiaClaimReviewReportDTO) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Кандидатов для сверки: \(value.possibleDifferences.count)")
                .font(.headline)

            if value.possibleDifferences.isEmpty {
                Text("Пары для сопоставления не найдены. Это не доказывает отсутствие противоречий.")
                    .font(.subheadline)
                    .foregroundStyle(JusticiaTheme.secondaryInk)
            }

            ForEach(value.possibleDifferences) { pair in
                VStack(alignment: .leading, spacing: 8) {
                    Label("Возможное расхождение — требует проверки", systemImage: "exclamationmark.triangle")
                        .font(.subheadline.weight(.medium))
                        .foregroundStyle(JusticiaTheme.orange)
                    claimRow(pair.left)
                    claimRow(pair.right)
                    Text(pair.reason)
                        .font(.caption)
                        .foregroundStyle(JusticiaTheme.secondaryInk)
                }
                .padding(12)
                .background(JusticiaTheme.surfaceMuted)
                .clipShape(RoundedRectangle(cornerRadius: 10))
            }

            Text("Все дословные выдержки: \(value.claims.count)")
                .font(.subheadline.weight(.semibold))
            ForEach(value.claims) { claim in
                claimRow(claim)
            }

            ForEach(value.warnings, id: \.self) { warning in
                Label(warning, systemImage: "info.circle")
                    .font(.caption)
                    .foregroundStyle(JusticiaTheme.secondaryInk)
            }
        }
        .padding(.top, 10)
    }

    private func claimRow(_ claim: JusticiaGroundedClaimDTO) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(claim.filename + " · " + (
                claim.physicalPage.map { "страница PDF \($0)" } ?? "страница не установлена"
            ))
            .font(.caption.weight(.semibold))
            Text("«" + claim.quote + "»")
                .font(.subheadline)
                .textSelection(.enabled)
            Text("Технический источник: " + claim.citation)
                .font(.caption2.monospaced())
                .foregroundStyle(JusticiaTheme.secondaryInk)
                .textSelection(.enabled)
        }
    }

    @MainActor
    private func inspect() async {
        guard let apiClient, let matterID = workspace.selectedMatterID, canInspect else { return }
        let currentSignature = signature
        let payload = request
        isWorking = true
        errorText = nil
        report = nil
        defer { isWorking = false }
        do {
            let result = try await apiClient.inspectClaimDifferences(
                matterID: matterID, request: payload
            )
            if currentSignature == signature && result.matterID == matterID {
                report = result
            }
        } catch {
            if currentSignature == signature {
                errorText = error.localizedDescription
            }
        }
    }

    @MainActor
    private func exportWord() async {
        guard let apiClient, let matterID = workspace.selectedMatterID,
              let report, report.matterID == matterID, !isWorking else { return }
        let currentSignature = signature
        isWorking = true
        errorText = nil
        defer { isWorking = false }
        do {
            let data = try await apiClient.exportClaimReview(matterID: matterID, report: report)
            guard currentSignature == signature else { return }
            #if os(macOS)
            let panel = NSSavePanel()
            panel.nameFieldStringValue = "Справка по расхождениям.docx"
            panel.allowedContentTypes = [UTType(filenameExtension: "docx")!]
            if panel.runModal() == .OK, let url = panel.url {
                try data.write(to: url, options: .atomic)
                successText = "Справка сохранена. Сверьте все выводы с оригиналами."
            }
            #else
            _ = data
            errorText = "В этой бета-версии экспорт DOCX доступен на macOS."
            #endif
        } catch {
            if currentSignature == signature {
                errorText = error.localizedDescription
            }
        }
    }
}
