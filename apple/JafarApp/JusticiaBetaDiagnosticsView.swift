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

            diagnosticRow("Версия", appVersion)
            diagnosticRow("Сборка", buildNumber)
            diagnosticRow("Система", systemVersion)
            diagnosticRow("Архитектура", architecture)
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

    private var appVersion: String {
        Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "—"
    }

    private var buildNumber: String {
        Bundle.main.object(forInfoDictionaryKey: "CFBundleVersion") as? String ?? "—"
    }

    private var systemVersion: String {
        ProcessInfo.processInfo.operatingSystemVersionString
    }

    private var architecture: String {
        #if arch(arm64)
        return "arm64"
        #elseif arch(x86_64)
        return "x86_64"
        #else
        return "unknown"
        #endif
    }

    private var report: String {
        [
            "Юстиция — beta diagnostics",
            "Version: \(appVersion)",
            "Build: \(buildNumber)",
            "OS: \(systemVersion)",
            "Architecture: \(architecture)",
            "Data note: no matter/document/transcript contents included"
        ].joined(separator: "\n")
    }

    private func copyDiagnostics() {
        #if os(macOS)
        NSPasteboard.general.clearContents()
        NSPasteboard.general.setString(report, forType: .string)
        #elseif os(iOS)
        UIPasteboard.general.string = report
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
