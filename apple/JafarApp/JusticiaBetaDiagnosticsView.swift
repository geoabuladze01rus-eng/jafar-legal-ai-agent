import SwiftUI

#if os(macOS)
import AppKit
#elseif os(iOS)
import UIKit
#endif

struct JusticiaBetaDiagnosticsView: View {
    @State private var copied = false

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                VStack(alignment: .leading, spacing: 3) {
                    Text("Диагностика beta")
                        .font(.headline)
                    Text("Техническая информация без содержимого дел и документов.")
                        .font(.caption)
                        .foregroundStyle(JusticiaTheme.secondaryInk)
                }
                Spacer()
                JusticiaPill(text: "Без юридических данных", color: JusticiaTheme.green)
            }

            diagnosticRow("Версия", JusticiaBetaDiagnosticsSnapshot.appVersion)
            diagnosticRow("Сборка", JusticiaBetaDiagnosticsSnapshot.buildNumber)
            diagnosticRow("Система", JusticiaBetaDiagnosticsSnapshot.systemVersion)
            diagnosticRow("Архитектура", JusticiaBetaDiagnosticsSnapshot.architecture)
            diagnosticRow("Продукт", "Юстиция")

            Divider()

            HStack {
                Label(
                    "Отчёт не включает названия дел, тексты документов, транскрипты или ключи доступа.",
                    systemImage: "lock.shield"
                )
                .font(.caption)
                .foregroundStyle(JusticiaTheme.secondaryInk)

                Spacer()

                Button {
                    copyDiagnostics()
                } label: {
                    Label(copied ? "Скопировано" : "Скопировать отчёт", systemImage: copied ? "checkmark" : "doc.on.doc")
                }
                .buttonStyle(.bordered)
            }
        }
    }

    private func copyDiagnostics() {
        #if os(macOS)
        NSPasteboard.general.clearContents()
        NSPasteboard.general.setString(JusticiaBetaDiagnosticsSnapshot.report, forType: .string)
        #elseif os(iOS)
        UIPasteboard.general.string = JusticiaBetaDiagnosticsSnapshot.report
        #endif
        copied = true
    }

    private func diagnosticRow(_ title: String, _ value: String) -> some View {
        HStack {
            Text(title)
                .font(.caption)
                .foregroundStyle(JusticiaTheme.secondaryInk)
                .frame(width: 110, alignment: .leading)
            Text(value)
                .font(.caption.monospaced())
                .textSelection(.enabled)
            Spacer()
        }
    }
}
