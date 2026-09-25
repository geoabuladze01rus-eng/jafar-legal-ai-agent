import SwiftUI

#if os(macOS)
import AppKit
#elseif os(iOS)
import UIKit
#endif

private struct JusticiaBuiltInTemplate: Identifiable, Hashable {
    let id: String
    let title: String
    let category: String
    let subtitle: String
    let icon: String
    let starterText: String
}

struct JusticiaTemplatesWorkspaceView: View {
    @State private var category = "Все"
    @State private var search = ""
    @State private var selectedTemplate: JusticiaBuiltInTemplate?
    @State private var copiedTemplateID: String?

    private let categories = ["Все", "Гражданские", "Арбитражные", "Уголовные", "Договоры"]

    private let templates: [JusticiaBuiltInTemplate] = [
        .init(
            id: "claim",
            title: "Исковое заявление",
            category: "Гражданские",
            subtitle: "Базовая структура процессуального документа",
            icon: "doc.text",
            starterText: """
            ИСКОВОЕ ЗАЯВЛЕНИЕ

            1. Стороны и подсудность
            [Заполните данные сторон и обоснование подсудности]

            2. Фактические обстоятельства
            [Изложите хронологию и существенные факты]

            3. Правовое обоснование
            [Укажите применимые нормы и позицию]

            4. Просительная часть
            [Сформулируйте требования]

            Приложения:
            [Перечень доказательств и документов]
            """
        ),
        .init(
            id: "motion",
            title: "Ходатайство",
            category: "Гражданские",
            subtitle: "Универсальная процессуальная структура",
            icon: "doc.badge.plus",
            starterText: """
            ХОДАТАЙСТВО

            По делу: [номер / наименование]

            Обстоятельства:
            [Кратко изложите основание обращения]

            Правовое основание:
            [Норма / процессуальное основание]

            ПРОШУ:
            [Чётко сформулируйте просьбу]

            Приложения:
            [При наличии]
            """
        ),
        .init(
            id: "appeal",
            title: "Апелляционная жалоба",
            category: "Гражданские",
            subtitle: "Каркас жалобы на судебный акт",
            icon: "arrow.up.doc",
            starterText: """
            АПЕЛЛЯЦИОННАЯ ЖАЛОБА

            Обжалуемый судебный акт:
            [Суд, дата, номер дела]

            Краткие обстоятельства:
            [Суть спора и выводы суда]

            Основания для отмены / изменения:
            [Аргументы со ссылками на материалы и нормы]

            ПРОШУ:
            [Требования заявителя]

            Приложения:
            [Перечень]
            """
        ),
        .init(
            id: "objections",
            title: "Возражения на иск",
            category: "Арбитражные",
            subtitle: "Структура отзыва / возражений",
            icon: "text.bubble",
            starterText: """
            ВОЗРАЖЕНИЯ НА ИСКОВОЕ ЗАЯВЛЕНИЕ

            Позиция по требованиям:
            [Какие требования признаются / оспариваются]

            Фактические возражения:
            [Факты и доказательства]

            Правовые возражения:
            [Нормы и судебные позиции]

            ПРОШУ:
            [Процессуальная просьба]

            Приложения:
            [Перечень]
            """
        ),
        .init(
            id: "criminal-motion",
            title: "Ходатайство по уголовному делу",
            category: "Уголовные",
            subtitle: "Каркас процессуального обращения",
            icon: "shield.lefthalf.filled",
            starterText: """
            ХОДАТАЙСТВО

            Уголовное дело № [номер]

            Процессуальное положение заявителя:
            [Укажите статус]

            Обстоятельства и основание:
            [Изложите факты и процессуальное основание]

            ПРОШУ:
            [Сформулируйте требуемое процессуальное действие]

            Приложения:
            [При наличии]
            """
        ),
        .init(
            id: "complaint",
            title: "Жалоба на процессуальное решение",
            category: "Уголовные",
            subtitle: "Структура жалобы на действие / бездействие",
            icon: "exclamationmark.bubble",
            starterText: """
            ЖАЛОБА

            Обжалуемое решение / действие:
            [Кем, когда и что совершено]

            Нарушенные права и обстоятельства:
            [Факты]

            Правовое обоснование:
            [Процессуальные нормы]

            ПРОШУ:
            [Требования заявителя]

            Приложения:
            [Перечень]
            """
        ),
        .init(
            id: "supply",
            title: "Договор поставки",
            category: "Договоры",
            subtitle: "Рабочая структура коммерческого договора",
            icon: "doc.on.clipboard",
            starterText: """
            ДОГОВОР ПОСТАВКИ

            1. Предмет договора
            2. Ассортимент, количество и качество
            3. Цена и порядок расчётов
            4. Сроки и порядок поставки
            5. Приёмка товара
            6. Ответственность сторон
            7. Форс-мажор
            8. Срок действия и расторжение
            9. Разрешение споров
            10. Реквизиты сторон
            """
        ),
        .init(
            id: "claim-letter",
            title: "Претензия",
            category: "Договоры",
            subtitle: "Досудебное требование",
            icon: "envelope",
            starterText: """
            ПРЕТЕНЗИЯ

            Основание обязательства:
            [Договор / иное основание]

            Нарушение:
            [Что произошло и когда]

            Расчёт требований:
            [Сумма / порядок расчёта]

            ТРЕБУЮ:
            [Конкретное требование и срок исполнения]

            Приложения:
            [Подтверждающие документы]
            """
        )
    ]

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            pageHeader(
                title: "Шаблоны документов",
                subtitle: "Встроенные основы документов. Это черновые структуры: факты, нормы и требования заполняются по конкретному делу."
            )

            HStack(spacing: 12) {
                Picker("Категория", selection: $category) {
                    ForEach(categories, id: \.self) { item in
                        Text(item).tag(item)
                    }
                }
                .pickerStyle(.segmented)

                HStack(spacing: 8) {
                    Image(systemName: "magnifyingglass")
                        .foregroundStyle(JusticiaTheme.secondaryInk)
                    TextField("Поиск шаблона", text: $search)
                        .textFieldStyle(.plain)
                }
                .padding(.horizontal, 10)
                .frame(width: 260, height: 34)
                .background(JusticiaTheme.surfaceMuted)
                .clipShape(RoundedRectangle(cornerRadius: 9))
            }

            if filteredTemplates.isEmpty {
                VStack(spacing: 10) {
                    JusticiaIconTile(systemName: "doc.on.doc", color: JusticiaTheme.secondaryInk)
                    Text("Шаблоны не найдены")
                        .font(.headline)
                    Text("Измените категорию или строку поиска.")
                        .font(.caption)
                        .foregroundStyle(JusticiaTheme.secondaryInk)
                }
                .frame(maxWidth: .infinity, minHeight: 260)
                .justiciaCard()
            } else {
                LazyVGrid(columns: [GridItem(.adaptive(minimum: 245), spacing: 14)], spacing: 14) {
                    ForEach(filteredTemplates) { template in
                        templateCard(template)
                    }
                }
            }

            Label(
                "Перед использованием проверьте подсудность, процессуальный порядок, актуальные нормы и фактические обстоятельства конкретного дела.",
                systemImage: "checkmark.shield"
            )
            .font(.caption)
            .foregroundStyle(JusticiaTheme.secondaryInk)
            .justiciaCard()
        }
        .sheet(item: $selectedTemplate) { template in
            JusticiaTemplatePreviewSheet(
                template: template,
                copied: copiedTemplateID == template.id,
                copyAction: {
                    copyToClipboard(template.starterText)
                    copiedTemplateID = template.id
                }
            )
            .frame(minWidth: 680, minHeight: 620)
        }
    }

    private var filteredTemplates: [JusticiaBuiltInTemplate] {
        let needle = search.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        return templates.filter { template in
            let categoryMatches = category == "Все" || template.category == category
            let searchMatches = needle.isEmpty
                || template.title.lowercased().contains(needle)
                || template.subtitle.lowercased().contains(needle)
            return categoryMatches && searchMatches
        }
    }

    private func templateCard(_ template: JusticiaBuiltInTemplate) -> some View {
        VStack(alignment: .leading, spacing: 13) {
            HStack {
                JusticiaIconTile(systemName: template.icon, color: JusticiaTheme.blue)
                Spacer()
                JusticiaPill(text: template.category, color: JusticiaTheme.violet)
            }

            Text(template.title)
                .font(.headline)
            Text(template.subtitle)
                .font(.caption)
                .foregroundStyle(JusticiaTheme.secondaryInk)
                .frame(minHeight: 34, alignment: .topLeading)

            Spacer()

            Button {
                selectedTemplate = template
            } label: {
                Label("Открыть структуру", systemImage: "doc.text.magnifyingglass")
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(.bordered)
        }
        .frame(minHeight: 170, alignment: .topLeading)
        .justiciaCard()
    }

    private func copyToClipboard(_ text: String) {
        #if os(macOS)
        NSPasteboard.general.clearContents()
        NSPasteboard.general.setString(text, forType: .string)
        #elseif os(iOS)
        UIPasteboard.general.string = text
        #endif
    }
}

private struct JusticiaTemplatePreviewSheet: View {
    @Environment(\.dismiss) private var dismiss
    let template: JusticiaBuiltInTemplate
    let copied: Bool
    let copyAction: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                VStack(alignment: .leading, spacing: 3) {
                    Text(template.title)
                        .font(.title2.bold())
                    Text("Встроенная черновая структура")
                        .font(.caption)
                        .foregroundStyle(JusticiaTheme.secondaryInk)
                }
                Spacer()
                Button {
                    dismiss()
                } label: {
                    Image(systemName: "xmark")
                }
                .buttonStyle(.plain)
            }

            TextEditor(text: .constant(template.starterText))
                .font(.body.monospaced())
                .padding(8)
                .background(JusticiaTheme.surface)
                .clipShape(RoundedRectangle(cornerRadius: 12))
                .overlay(
                    RoundedRectangle(cornerRadius: 12)
                        .stroke(JusticiaTheme.border, lineWidth: 1)
                )

            HStack {
                Label(
                    "Структура не подставляет факты и нормы автоматически.",
                    systemImage: "exclamationmark.triangle"
                )
                .font(.caption)
                .foregroundStyle(JusticiaTheme.secondaryInk)

                Spacer()

                Button {
                    copyAction()
                } label: {
                    Label(copied ? "Скопировано" : "Скопировать", systemImage: copied ? "checkmark" : "doc.on.doc")
                }
                .buttonStyle(.borderedProminent)
            }
        }
        .padding(22)
        .background(JusticiaTheme.canvas)
    }
}
