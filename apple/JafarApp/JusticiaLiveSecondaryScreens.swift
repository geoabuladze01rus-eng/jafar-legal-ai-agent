import SwiftUI

struct JusticiaLiveAnalyticsView: View {
    @ObservedObject var workspace: JusticiaWorkspaceStore

    private let columns = [GridItem(.adaptive(minimum: 220), spacing: 14)]

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            pageHeader(
                title: "Аналитика",
                subtitle: "Сводка формируется только по реальным делам из локального хранилища."
            )

            LazyVGrid(columns: columns, spacing: 14) {
                metric("Всего дел", "\(workspace.matters.count)", "briefcase", JusticiaTheme.blue)
                metric("Активные", "\(activeCount)", "checkmark.shield", JusticiaTheme.green)
                metric("Со сроками", "\(mattersWithDeadlines)", "calendar.badge.clock", JusticiaTheme.orange)
                metric("Сроков всего", "\(deadlineCount)", "clock", JusticiaTheme.violet)
            }

            HStack(alignment: .top, spacing: 14) {
                VStack(alignment: .leading, spacing: 14) {
                    Text("По категориям")
                        .font(.headline)

                    if workspace.matters.isEmpty {
                        Text("После создания дел здесь появится распределение по направлениям практики.")
                            .font(.subheadline)
                            .foregroundStyle(JusticiaTheme.secondaryInk)
                    } else {
                        ForEach(categoryBreakdown, id: \.0) { item in
                            HStack {
                                Circle()
                                    .fill(categoryColor(item.0))
                                    .frame(width: 9, height: 9)
                                Text(localizedMatterType(item.0))
                                    .font(.subheadline)
                                Spacer()
                                Text("\(item.1)")
                                    .font(.subheadline.weight(.semibold))
                            }
                        }
                    }
                }
                .justiciaCard()
                .frame(maxWidth: .infinity)

                VStack(alignment: .leading, spacing: 14) {
                    Text("Последние дела")
                        .font(.headline)

                    if workspace.matters.isEmpty {
                        Text("Данных пока нет.")
                            .font(.subheadline)
                            .foregroundStyle(JusticiaTheme.secondaryInk)
                    } else {
                        ForEach(workspace.matters.prefix(6)) { matter in
                            HStack(spacing: 10) {
                                JusticiaIconTile(systemName: "briefcase", color: JusticiaTheme.blue, size: 30)
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(matter.displayNumber)
                                        .font(.caption.weight(.semibold))
                                    Text(matter.title)
                                        .font(.caption2)
                                        .foregroundStyle(JusticiaTheme.secondaryInk)
                                        .lineLimit(1)
                                }
                                Spacer()
                                JusticiaPill(text: matter.displayStatus, color: JusticiaTheme.green)
                            }
                        }
                    }
                }
                .justiciaCard()
                .frame(maxWidth: .infinity)
            }

            VStack(alignment: .leading, spacing: 12) {
                Text("Принцип аналитики")
                    .font(.headline)
                Label(
                    "«Юстиция» не подменяет отсутствующие данные демонстрационными значениями: показатели на этом экране рассчитываются из вашей локальной базы.",
                    systemImage: "checkmark.shield"
                )
                .font(.subheadline)
                .foregroundStyle(JusticiaTheme.secondaryInk)
            }
            .justiciaCard()
        }
        .task {
            if workspace.matters.isEmpty {
                await workspace.refresh()
            }
        }
    }

    private var activeCount: Int {
        workspace.matters.filter { $0.status.lowercased() == "active" }.count
    }

    private var mattersWithDeadlines: Int {
        workspace.matters.filter { !$0.deadlines.isEmpty }.count
    }

    private var deadlineCount: Int {
        workspace.matters.reduce(0) { $0 + $1.deadlines.count }
    }

    private var categoryBreakdown: [(String, Int)] {
        let grouped = Dictionary(grouping: workspace.matters, by: \.matterType)
        return grouped.map { ($0.key, $0.value.count) }.sorted { $0.1 > $1.1 }
    }

    private func metric(_ title: String, _ value: String, _ icon: String, _ color: Color) -> some View {
        HStack {
            JusticiaIconTile(systemName: icon, color: color)
            VStack(alignment: .leading, spacing: 3) {
                Text(value)
                    .font(.title2.bold())
                Text(title)
                    .font(.caption)
                    .foregroundStyle(JusticiaTheme.secondaryInk)
            }
            Spacer()
        }
        .justiciaCard()
    }

    private func localizedMatterType(_ type: String) -> String {
        switch type {
        case "criminal": "Уголовные"
        case "arbitration": "Арбитражные"
        case "civil": "Гражданские"
        case "administrative": "Административные"
        default: "Общие"
        }
    }

    private func categoryColor(_ type: String) -> Color {
        switch type {
        case "criminal": JusticiaTheme.red
        case "arbitration": JusticiaTheme.blue
        case "civil": JusticiaTheme.green
        case "administrative": JusticiaTheme.orange
        default: JusticiaTheme.violet
        }
    }
}

struct JusticiaLiveDeadlinesView: View {
    @ObservedObject var workspace: JusticiaWorkspaceStore
    @State private var query = ""

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            pageHeader(
                title: "Сроки",
                subtitle: "Процессуальные сроки из локальных карточек дел — без фиктивных календарных событий."
            )

            HStack {
                HStack {
                    Image(systemName: "magnifyingglass")
                        .foregroundStyle(JusticiaTheme.secondaryInk)
                    TextField("Поиск по срокам или номеру дела", text: $query)
                        .textFieldStyle(.plain)
                }
                .padding(.horizontal, 12)
                .frame(maxWidth: 520)
                .frame(height: 38)
                .background(JusticiaTheme.surfaceMuted)
                .clipShape(RoundedRectangle(cornerRadius: 10))

                Spacer()

                JusticiaPill(text: "Всего: \(allDeadlines.count)", color: JusticiaTheme.blue)
            }

            if filteredDeadlines.isEmpty {
                VStack(spacing: 10) {
                    JusticiaIconTile(systemName: "calendar.badge.clock", color: JusticiaTheme.secondaryInk, size: 42)
                    Text(allDeadlines.isEmpty ? "Сроки пока не добавлены" : "По запросу ничего не найдено")
                        .font(.headline)
                    Text(
                        allDeadlines.isEmpty
                            ? "Сроки, сохранённые в делах или извлечённые из документов, появятся здесь."
                            : "Измените строку поиска."
                    )
                    .font(.subheadline)
                    .foregroundStyle(JusticiaTheme.secondaryInk)
                }
                .frame(maxWidth: .infinity, minHeight: 260)
                .justiciaCard()
            } else {
                VStack(spacing: 0) {
                    headerRow
                    Divider()
                    ForEach(Array(filteredDeadlines.enumerated()), id: \.offset) { index, item in
                        deadlineRow(item)
                        if index < filteredDeadlines.count - 1 {
                            Divider()
                        }
                    }
                }
                .justiciaCard(padding: 0)
            }
        }
        .task {
            if workspace.matters.isEmpty {
                await workspace.refresh()
            }
        }
    }

    private var allDeadlines: [(JusticiaMatterDTO, JusticiaDeadlineDTO)] {
        workspace.matters.flatMap { matter in
            matter.deadlines.map { (matter, $0) }
        }
        .sorted { lhs, rhs in
            switch (lhs.1.dueDate, rhs.1.dueDate) {
            case let (a?, b?): a < b
            case (.some, .none): true
            case (.none, .some): false
            case (.none, .none): lhs.1.title < rhs.1.title
            }
        }
    }

    private var filteredDeadlines: [(JusticiaMatterDTO, JusticiaDeadlineDTO)] {
        let needle = query.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        guard !needle.isEmpty else { return allDeadlines }
        return allDeadlines.filter { matter, deadline in
            deadline.title.lowercased().contains(needle)
                || matter.displayNumber.lowercased().contains(needle)
                || matter.title.lowercased().contains(needle)
        }
    }

    private var headerRow: some View {
        HStack {
            Text("Срок")
                .frame(width: 120, alignment: .leading)
            Text("Событие")
                .frame(maxWidth: .infinity, alignment: .leading)
            Text("Дело")
                .frame(width: 200, alignment: .leading)
            Text("Уверенность")
                .frame(width: 120, alignment: .leading)
        }
        .font(.caption.bold())
        .foregroundStyle(JusticiaTheme.secondaryInk)
        .padding(14)
    }

    private func deadlineRow(_ item: (JusticiaMatterDTO, JusticiaDeadlineDTO)) -> some View {
        HStack {
            Text(item.1.dueDate ?? "Не указана")
                .font(.caption.monospacedDigit())
                .frame(width: 120, alignment: .leading)
            VStack(alignment: .leading, spacing: 2) {
                Text(item.1.title)
                    .font(.subheadline.weight(.semibold))
                if let source = item.1.sourceText, !source.isEmpty {
                    Text(source)
                        .font(.caption2)
                        .foregroundStyle(JusticiaTheme.secondaryInk)
                        .lineLimit(1)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            Text(item.0.displayNumber)
                .font(.caption)
                .frame(width: 200, alignment: .leading)
            Text(String(format: "%.0f%%", item.1.confidence * 100))
                .font(.caption.weight(.semibold))
                .foregroundStyle(item.1.confidence >= 0.8 ? JusticiaTheme.green : JusticiaTheme.orange)
                .frame(width: 120, alignment: .leading)
        }
        .padding(14)
    }
}

struct JusticiaPublishingWorkspaceView: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            pageHeader(
                title: "Автопубликации",
                subtitle: "Публикация во внешние каналы остаётся действием с обязательным человеческим подтверждением."
            )

            HStack(spacing: 14) {
                safetyCard(
                    "Черновик сначала",
                    "ИИ может подготовить материал, но не должен самовольно публиковать его.",
                    "doc.badge.ellipsis",
                    JusticiaTheme.blue
                )
                safetyCard(
                    "Подтверждение",
                    "Перед внешней отправкой пользователь должен явно подтвердить действие.",
                    "person.badge.shield.checkmark",
                    JusticiaTheme.green
                )
                safetyCard(
                    "Без дублей",
                    "Неоднозначный результат отправки должен блокировать автоматический повтор.",
                    "checkmark.circle",
                    JusticiaTheme.orange
                )
            }

            VStack(spacing: 10) {
                JusticiaIconTile(systemName: "paperplane", color: JusticiaTheme.secondaryInk, size: 44)
                Text("Очередь публикаций пуста")
                    .font(.headline)
                Text("Реальные публикации здесь появятся после подключения UI к защищённому Telegram publication runtime. Фиктивные опубликованные записи не показываются.")
                    .font(.subheadline)
                    .foregroundStyle(JusticiaTheme.secondaryInk)
                    .multilineTextAlignment(.center)
                    .frame(maxWidth: 620)
            }
            .frame(maxWidth: .infinity, minHeight: 300)
            .justiciaCard()
        }
    }

    private func safetyCard(_ title: String, _ text: String, _ icon: String, _ color: Color) -> some View {
        HStack(alignment: .top, spacing: 12) {
            JusticiaIconTile(systemName: icon, color: color)
            VStack(alignment: .leading, spacing: 4) {
                Text(title)
                    .font(.subheadline.weight(.semibold))
                Text(text)
                    .font(.caption)
                    .foregroundStyle(JusticiaTheme.secondaryInk)
            }
            Spacer()
        }
        .justiciaCard()
        .frame(maxWidth: .infinity)
    }
}
