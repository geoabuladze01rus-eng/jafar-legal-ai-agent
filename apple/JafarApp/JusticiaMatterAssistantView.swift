import SwiftUI

struct JusticiaMatterAssistantView: View {
    @Environment(\.dismiss) private var dismiss

    let matter: JusticiaMatterDTO
    let apiClient: JusticiaAPIClient

    @State private var question = ""
    @State private var result: JusticiaMatterResearchResponseDTO?
    @State private var isLoading = false
    @State private var errorMessage: String?

    private let quickQuestions = [
        "Сформулируй ключевые факты по материалам дела",
        "Какие слабые места есть в нашей позиции?",
        "Какие противоречия требуют проверки?",
        "Каких доказательств может не хватать?"
    ]

    var body: some View {
        VStack(spacing: 0) {
            header
            Divider()

            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    scopeCard
                    quickPrompts
                    questionComposer

                    if isLoading {
                        HStack(spacing: 10) {
                            ProgressView()
                            Text("Исследуем только материалы выбранного дела…")
                                .font(.subheadline)
                                .foregroundStyle(JusticiaTheme.secondaryInk)
                        }
                        .frame(maxWidth: .infinity, minHeight: 90)
                        .justiciaCard()
                    }

                    if let errorMessage {
                        errorCard(errorMessage)
                    }

                    if let result {
                        answerCard(result)
                        if !result.citations.isEmpty {
                            citationsCard(result.citations)
                        }
                        if !result.contradictions.isEmpty {
                            contradictionsCard(result.contradictions)
                        }
                    }
                }
                .padding(20)
            }
            .background(JusticiaTheme.canvas)
        }
        .frame(minWidth: 780, minHeight: 680)
    }

    private var header: some View {
        HStack(spacing: 12) {
            JusticiaIconTile(systemName: "sparkles", color: JusticiaTheme.violet, size: 40)

            VStack(alignment: .leading, spacing: 2) {
                Text("ИИ-помощник по делу")
                    .font(.title2.bold())
                    .foregroundStyle(JusticiaTheme.ink)
                Text(matter.displayNumber + " · " + matter.title)
                    .font(.caption)
                    .foregroundStyle(JusticiaTheme.secondaryInk)
                    .lineLimit(1)
            }

            Spacer()

            JusticiaPill(text: "Локальный контекст дела", color: JusticiaTheme.green)

            Button {
                dismiss()
            } label: {
                Image(systemName: "xmark")
            }
            .buttonStyle(.plain)
        }
        .padding(18)
        .background(JusticiaTheme.surface)
    }

    private var scopeCard: some View {
        HStack(alignment: .top, spacing: 12) {
            JusticiaIconTile(systemName: "lock.shield", color: JusticiaTheme.green, size: 36)

            VStack(alignment: .leading, spacing: 4) {
                Text("Контекст ограничен выбранным делом")
                    .font(.subheadline.weight(.semibold))
                Text("Ответ строится по локально проиндексированным документам этого Matter. «Юстиция» возвращает ссылки на использованные фрагменты и не должна подмешивать материалы других дел.")
                    .font(.caption)
                    .foregroundStyle(JusticiaTheme.secondaryInk)
                    .lineSpacing(3)
            }

            Spacer()
        }
        .justiciaCard()
    }

    private var quickPrompts: some View {
        VStack(alignment: .leading, spacing: 9) {
            Text("Быстрые вопросы")
                .font(.headline)

            LazyVGrid(columns: [GridItem(.adaptive(minimum: 240), spacing: 8)], spacing: 8) {
                ForEach(quickQuestions, id: \.self) { prompt in
                    Button {
                        question = prompt
                    } label: {
                        HStack(alignment: .top, spacing: 8) {
                            Image(systemName: "sparkles")
                                .foregroundStyle(JusticiaTheme.blue)
                            Text(prompt)
                                .font(.caption)
                                .foregroundStyle(JusticiaTheme.ink)
                                .multilineTextAlignment(.leading)
                            Spacer()
                        }
                        .padding(10)
                        .background(JusticiaTheme.surfaceMuted)
                        .clipShape(RoundedRectangle(cornerRadius: 10))
                    }
                    .buttonStyle(.plain)
                }
            }
        }
        .justiciaCard()
    }

    private var questionComposer: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Вопрос по материалам дела")
                .font(.headline)

            TextEditor(text: $question)
                .font(.body)
                .frame(minHeight: 100)
                .padding(8)
                .background(JusticiaTheme.surface)
                .clipShape(RoundedRectangle(cornerRadius: 10))
                .overlay(
                    RoundedRectangle(cornerRadius: 10)
                        .stroke(JusticiaTheme.border, lineWidth: 1)
                )
                .overlay(alignment: .topLeading) {
                    if question.isEmpty {
                        Text("Например: какие факты подтверждают исполнение обязательства и где есть пробелы?")
                            .font(.body)
                            .foregroundStyle(JusticiaTheme.secondaryInk.opacity(0.65))
                            .padding(.horizontal, 13)
                            .padding(.vertical, 16)
                            .allowsHitTesting(false)
                    }
                }

            HStack {
                Text("Результат не заменяет проверку первичных материалов юристом.")
                    .font(.caption)
                    .foregroundStyle(JusticiaTheme.secondaryInk)

                Spacer()

                Button {
                    runResearch()
                } label: {
                    if isLoading {
                        ProgressView()
                    } else {
                        Label("Исследовать", systemImage: "sparkles")
                    }
                }
                .buttonStyle(.borderedProminent)
                .disabled(
                    isLoading
                        || question.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
                )
                .keyboardShortcut(.defaultAction)
            }
        }
        .justiciaCard()
    }

    private func answerCard(_ response: JusticiaMatterResearchResponseDTO) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                JusticiaIconTile(systemName: "text.quote", color: JusticiaTheme.blue, size: 34)
                VStack(alignment: .leading, spacing: 2) {
                    Text("Ответ")
                        .font(.headline)
                    Text("Использовано фрагментов: \(response.retrievedChunks)")
                        .font(.caption)
                        .foregroundStyle(JusticiaTheme.secondaryInk)
                }
                Spacer()
            }

            Text(response.answer)
                .font(.body)
                .lineSpacing(5)
                .textSelection(.enabled)
                .frame(maxWidth: .infinity, alignment: .leading)

            if response.retrievedChunks == 0 {
                Label(
                    "По запросу не найдено релевантных фрагментов. Проверьте, что документы импортированы и проиндексированы.",
                    systemImage: "exclamationmark.triangle"
                )
                .font(.caption)
                .foregroundStyle(JusticiaTheme.orange)
            }
        }
        .justiciaCard()
    }

    private func citationsCard(_ citations: [String]) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Text("Источники")
                    .font(.headline)
                Spacer()
                JusticiaPill(text: "\(citations.count)", color: JusticiaTheme.blue)
            }

            ForEach(citations, id: \.self) { citation in
                HStack(alignment: .top, spacing: 8) {
                    Image(systemName: "quote.opening")
                        .foregroundStyle(JusticiaTheme.blue)
                    Text(citation)
                        .font(.caption.monospaced())
                        .textSelection(.enabled)
                    Spacer()
                }
                .padding(9)
                .background(JusticiaTheme.surfaceMuted.opacity(0.75))
                .clipShape(RoundedRectangle(cornerRadius: 9))
            }
        }
        .justiciaCard()
    }

    private func contradictionsCard(_ contradictions: [[String: JSONValue]]) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Text("Противоречия и пробелы")
                    .font(.headline)
                Spacer()
                JusticiaPill(text: "\(contradictions.count)", color: JusticiaTheme.orange)
            }

            ForEach(Array(contradictions.enumerated()), id: \.offset) { _, item in
                contradictionRow(item)
            }
        }
        .justiciaCard()
    }

    private func contradictionRow(_ item: [String: JSONValue]) -> some View {
        let type = stringValue(item["type"])
        let topic = stringValue(item["topic"])
        let severity = stringValue(item["severity"])
        let isGap = type == "evidence_gap"

        return VStack(alignment: .leading, spacing: 7) {
            HStack {
                Image(systemName: isGap ? "questionmark.folder" : "exclamationmark.triangle")
                    .foregroundStyle(isGap ? JusticiaTheme.orange : JusticiaTheme.red)
                Text(topic.isEmpty ? (isGap ? "Пробел в доказательствах" : "Противоречие") : topic)
                    .font(.subheadline.weight(.semibold))
                Spacer()
                if !severity.isEmpty {
                    JusticiaPill(text: localizedSeverity(severity), color: severityColor(severity))
                }
            }

            if isGap {
                let description = stringValue(item["description"])
                if !description.isEmpty {
                    Text(description)
                        .font(.caption)
                        .foregroundStyle(JusticiaTheme.secondaryInk)
                }
            } else {
                let left = stringValue(item["left"])
                let right = stringValue(item["right"])
                if !left.isEmpty {
                    Text("Версия 1: " + left)
                        .font(.caption)
                        .textSelection(.enabled)
                }
                if !right.isEmpty {
                    Text("Версия 2: " + right)
                        .font(.caption)
                        .textSelection(.enabled)
                }
            }
        }
        .padding(10)
        .background(JusticiaTheme.surfaceMuted.opacity(0.75))
        .clipShape(RoundedRectangle(cornerRadius: 10))
    }

    private func errorCard(_ message: String) -> some View {
        HStack(alignment: .top, spacing: 10) {
            Image(systemName: "exclamationmark.triangle.fill")
                .foregroundStyle(JusticiaTheme.red)
            VStack(alignment: .leading, spacing: 3) {
                Text("Исследование не выполнено")
                    .font(.subheadline.weight(.semibold))
                Text(message)
                    .font(.caption)
                    .foregroundStyle(JusticiaTheme.secondaryInk)
            }
            Spacer()
        }
        .justiciaCard()
    }

    private func runResearch() {
        let normalized = question.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !normalized.isEmpty, !isLoading else { return }

        isLoading = true
        errorMessage = nil
        result = nil

        Task {
            do {
                let response = try await apiClient.researchMatter(
                    matterID: matter.id,
                    question: normalized
                )
                await MainActor.run {
                    result = response
                    isLoading = false
                }
            } catch {
                await MainActor.run {
                    errorMessage = error.localizedDescription
                    isLoading = false
                }
            }
        }
    }

    private func stringValue(_ value: JSONValue?) -> String {
        guard let value else { return "" }
        switch value {
        case .string(let string): return string
        case .number(let number): return String(number)
        case .bool(let bool): return bool ? "true" : "false"
        case .array(let values):
            return values.map { stringValue($0) }.joined(separator: ", ")
        case .object:
            return ""
        case .null:
            return ""
        }
    }

    private func localizedSeverity(_ severity: String) -> String {
        switch severity.lowercased() {
        case "high": return "Высокая"
        case "medium": return "Средняя"
        case "low": return "Низкая"
        default: return severity
        }
    }

    private func severityColor(_ severity: String) -> Color {
        switch severity.lowercased() {
        case "high": return JusticiaTheme.red
        case "medium": return JusticiaTheme.orange
        case "low": return JusticiaTheme.green
        default: return JusticiaTheme.secondaryInk
        }
    }
}
