import SwiftUI

#if os(macOS)
import AppKit
#elseif os(iOS)
import UIKit
#endif

private enum JusticiaBetaFeedbackCategory: String, CaseIterable, Identifiable {
    case bug = "Ошибка"
    case usability = "Удобство"
    case idea = "Идея"
    case privacy = "Конфиденциальность"

    var id: String { rawValue }

    var icon: String {
        switch self {
        case .bug: return "ladybug"
        case .usability: return "hand.tap"
        case .idea: return "lightbulb"
        case .privacy: return "lock.shield"
        }
    }
}

struct JusticiaBetaFeedbackView: View {
    @State private var category: JusticiaBetaFeedbackCategory = .bug
    @State private var note = ""
    @State private var includeDiagnostics = true
    @State private var copied = false

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack {
                VStack(alignment: .leading, spacing: 3) {
                    Text("Обратная связь beta")
                        .font(.headline)
                    Text("Опишите проблему или идею. Ничего не отправляется автоматически.")
                        .font(.caption)
                        .foregroundStyle(JusticiaTheme.secondaryInk)
                }

                Spacer()

                JusticiaPill(text: "Ручная отправка", color: JusticiaTheme.blue)
            }

            Picker("Тип", selection: $category) {
                ForEach(JusticiaBetaFeedbackCategory.allCases) { item in
                    Label(item.rawValue, systemImage: item.icon)
                        .tag(item)
                }
            }
            .pickerStyle(.segmented)

            TextEditor(text: $note)
                .font(.body)
                .frame(minHeight: 120)
                .padding(8)
                .background(JusticiaTheme.surface)
                .clipShape(RoundedRectangle(cornerRadius: 10))
                .overlay(
                    RoundedRectangle(cornerRadius: 10)
                        .stroke(JusticiaTheme.border, lineWidth: 1)
                )
                .overlay(alignment: .topLeading) {
                    if note.isEmpty {
                        Text("Что произошло? Что ожидали? Что можно улучшить?")
                            .font(.body)
                            .foregroundStyle(JusticiaTheme.secondaryInk.opacity(0.65))
                            .padding(.horizontal, 13)
                            .padding(.vertical, 16)
                            .allowsHitTesting(false)
                    }
                }

            Toggle("Добавить техническую диагностику", isOn: $includeDiagnostics)

            Label(
                "Не вставляйте в отзыв ФИО клиентов, тексты документов, номера дел, аудиозаписи, пароли, токены и иные конфиденциальные сведения.",
                systemImage: "exclamationmark.triangle"
            )
            .font(.caption)
            .foregroundStyle(JusticiaTheme.orange)

            HStack {
                Text(previewSummary)
                    .font(.caption)
                    .foregroundStyle(JusticiaTheme.secondaryInk)

                Spacer()

                Button {
                    copyFeedback()
                } label: {
                    Label(
                        copied ? "Скопировано" : "Скопировать пакет",
                        systemImage: copied ? "checkmark" : "doc.on.doc"
                    )
                }
                .buttonStyle(.borderedProminent)
                .disabled(note.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
            }
        }
    }

    private var previewSummary: String {
        includeDiagnostics
            ? "Отзыв + безопасная диагностика"
            : "Только текст отзыва"
    }

    private var feedbackPackage: String {
        var parts = [
            "Юстиция — beta feedback",
            "Категория: \(category.rawValue)",
            "",
            "Сообщение:",
            note.trimmingCharacters(in: .whitespacesAndNewlines)
        ]

        if includeDiagnostics {
            parts += [
                "",
                JusticiaBetaDiagnosticsSnapshot.report
            ]
        }

        parts += [
            "",
            "Privacy note: пакет сформирован вручную; содержимое дел, документов и транскриптов приложением не добавляется."
        ]

        return parts.joined(separator: "\n")
    }

    private func copyFeedback() {
        #if os(macOS)
        NSPasteboard.general.clearContents()
        NSPasteboard.general.setString(feedbackPackage, forType: .string)
        #elseif os(iOS)
        UIPasteboard.general.string = feedbackPackage
        #endif
        copied = true
    }
}
