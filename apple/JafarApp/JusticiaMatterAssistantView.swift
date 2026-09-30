import SwiftUI

struct JusticiaMatterAssistantView: View {
    @ObservedObject var workspace: JusticiaWorkspaceStore
    @State private var question = ""

    private let quickQuestions = [
        "Какие факты подтверждаются материалами дела?",
        "Какие слабые места есть в позиции?",
        "Есть ли противоречия в документах?",
        "Какие обстоятельства требуют дополнительной проверки?"
    ]

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack(alignment: .top) {
                HStack(spacing: 10) {
                    JusticiaIconTile(systemName: "sparkles", color: JusticiaTheme.violet, size: 36)
                    VStack(alignment: .leading, spacing: 3) {
                        Text("ИИ-помощник по делу")
                            .font(.headline)
                        Text("Ответ только по материалам выбранного дела с указанием локальных источников.")
                            .font(.caption)
                            .foregroundStyle(JusticiaTheme.secondaryInk)
                    }
                }
                Spacer()
                JusticiaPill(text: "Локально", color: JusticiaTheme.green)
            }

            if workspace.documents.isEmpty {
                Label(
                    "Сначала добавьте документы в это дело — помощник не будет придумывать ответ без материалов.",
                    systemImage: "doc.badge.plus"
                )
                .font(.subheadline)
                .foregroundStyle(JusticiaTheme.secondaryInk)
                .padding(.vertical, 8)
            } else {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 8) {
                        ForEach(quickQuestions, id: \.self) { prompt in
                            Button {
                                question = prompt
                            } label: {
                                Text(prompt)
                                    .font(.caption)
                                    .lineLimit(1)
                                    .padding(.horizontal, 10)
                                    .padding(.vertical, 7)
                                    .background(JusticiaTheme.surfaceMuted)
                                    .clipShape(Capsule())
                            }
                            .buttonStyle(.plain)
                        }
                    }
                }

                HStack(alignment: .bottom, spacing: 10) {
                    TextField("Задайте вопрос по материалам дела…", text: $question, axis: .vertical)
                        .textFieldStyle(.plain)
                        .lineLimit(2...5)
                        .padding(11)
                        .background(JusticiaTheme.surfaceMuted)
                        .clipShape(RoundedRectangle(cornerRadius: 10))

                    Button {
                        Task {
                            await workspace.researchSelectedMatter(question: question)
                        }
                    } label: {
                        if workspace.isResearching {
                            ProgressView()
                                .frame(width: 84)
                        } else {
                            Label("Спросить", systemImage: "arrow.up.circle.fill")
                        }
                    }
                    .buttonStyle(.borderedProminent)
                    .disabled(
                        question.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
                            || workspace.isResearching
                            || workspace.documents.isEmpty
                    )
                }

                if workspace.isResearching {
                    HStack(spacing: 10) {
                        ProgressView()
                        Text("Ищу релевантные фрагменты только внутри выбранного дела…")
                            .font(.caption)
                            .foregroundStyle(JusticiaTheme.secondaryInk)
                    }
                }

                if !workspace.researchAnswer.isEmpty {
                    Divider()

                    VStack(alignment: .leading, spacing: 10) {
                        HStack {
                            Text("Ответ")
                                .font(.subheadline.weight(.semibold))
                            Spacer()
                            JusticiaPill(
                                text: "Фрагментов: \(workspace.researchRetrievedChunks)",
                                color: JusticiaTheme.blue
                            )
                        }

                        Text(workspace.researchAnswer)
                            .font(.subheadline)
                            .lineSpacing(5)
                            .textSelection(.enabled)

                        if !workspace.researchCitations.isEmpty {
                            VStack(alignment: .leading, spacing: 7) {
                                Text("Источники")
                                    .font(.caption.weight(.semibold))
                                    .foregroundStyle(JusticiaTheme.secondaryInk)

                                ForEach(workspace.researchCitations, id: \.self) { citation in
                                    HStack(alignment: .top, spacing: 8) {
                                        Image(systemName: "quote.opening")
                                            .foregroundStyle(JusticiaTheme.blue)
                                        Text(citation)
                                            .font(.caption.monospaced())
                                            .textSelection(.enabled)
                                        Spacer()
                                    }
                                }
                            }
                        }
                    }
                }

                if let error = workspace.errorMessage,
                   !error.isEmpty,
                   !workspace.isResearching {
                    HStack(spacing: 8) {
                        Image(systemName: "exclamationmark.triangle.fill")
                            .foregroundStyle(JusticiaTheme.red)
                        Text(error)
                            .font(.caption)
                            .foregroundStyle(JusticiaTheme.red)
                    }
                }

                Label(
                    "Помощник не использует материалы других дел. Вывод проверяйте по указанным фрагментам перед использованием в работе.",
                    systemImage: "checkmark.shield"
                )
                .font(.caption)
                .foregroundStyle(JusticiaTheme.secondaryInk)
            }
        }
        .justiciaCard()
    }
}
