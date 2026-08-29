import SwiftUI

private enum JusticeDestination: String, CaseIterable, Identifiable {
    case home, matters, documents, evidence, timeline, contradictions, authorities
    case council, position, hearing, court, approvals, costs, settings

    var id: String { rawValue }
    var title: String {
        switch self {
        case .home: "Главная"; case .matters: "Дела"; case .documents: "Документы"
        case .evidence: "Доказательства"; case .timeline: "Хронология"
        case .contradictions: "Противоречия"; case .authorities: "Судебная практика"
        case .council: "Совет моделей"; case .position: "Правовая позиция"
        case .hearing: "Подготовка к заседанию"; case .court: "Court Mode"
        case .approvals: "Решения"; case .costs: "Использование AI"; case .settings: "Настройки"
        }
    }
    var icon: String {
        switch self {
        case .home: "house.fill"; case .matters: "briefcase.fill"; case .documents: "doc.text.fill"
        case .evidence: "link"; case .timeline: "clock.arrow.circlepath"
        case .contradictions: "exclamationmark.triangle.fill"; case .authorities: "building.columns.fill"
        case .council: "person.3.fill"; case .position: "text.book.closed.fill"
        case .hearing: "checklist"; case .court: "gavel.fill"; case .approvals: "checkmark.seal.fill"
        case .costs: "chart.bar.xaxis"; case .settings: "gearshape.fill"
        }
    }
    static var primary: [JusticeDestination] { [.home, .matters, .documents, .evidence, .authorities, .council, .approvals, .costs, .settings] }
}

struct JusticeWorkspaceView: View {
    @ObservedObject var dashboard: DashboardStore
    @Environment(\.horizontalSizeClass) private var sizeClass
    @State private var selection: JusticeDestination = .home
    @State private var selectedMatter: DashboardMatter?
    @State private var searchText = ""

    var body: some View {
        Group {
            if sizeClass == .compact {
                compactLayout
            } else {
                regularLayout
            }
        }
        .preferredColorScheme(.dark)
    }

    private var regularLayout: some View {
        NavigationSplitView {
            sidebar
        } detail: {
            destinationView(selection)
        }
        .searchable(text: $searchText, placement: .sidebar, prompt: "Поиск по делам и документам")
        .frame(minWidth: 760, minHeight: 560)
    }

    private var compactLayout: some View {
        TabView(selection: $selection) {
            destinationView(.home).tabItem { Label("Главная", systemImage: "house.fill") }.tag(JusticeDestination.home)
            destinationView(.matters).tabItem { Label("Дела", systemImage: "briefcase.fill") }.tag(JusticeDestination.matters)
            destinationView(.council).tabItem { Label("Юстиция", systemImage: "scalemass.fill") }.tag(JusticeDestination.council)
            destinationView(.approvals).tabItem { Label("Решения", systemImage: "checkmark.seal.fill") }.tag(JusticeDestination.approvals)
            destinationView(.settings).tabItem { Label("Ещё", systemImage: "ellipsis.circle.fill") }.tag(JusticeDestination.settings)
        }
        .tint(JafarPalette.accentGold)
    }

    private var sidebar: some View {
        List {
            Section {
                ForEach(JusticeDestination.primary) { destination in
                    Button { selection = destination } label: {
                        Label(destination.title, systemImage: destination.icon)
                    }.buttonStyle(.plain)
                }
            } header: {
                VStack(alignment: .leading, spacing: 4) {
                    Text("ЮСТИЦИЯ AI").font(JusticeTypography.title).foregroundStyle(JafarPalette.textPrimary)
                    Text("Интеллектуальная система адвоката").font(JusticeTypography.caption).foregroundStyle(JafarPalette.textSecondary)
                }.padding(.vertical, JusticeSpacing.sm)
            }
            Section("Работа по делу") {
                ForEach([JusticeDestination.timeline, .contradictions, .position, .hearing, .court]) { destination in
                    Button { selection = destination } label: {
                        Label(destination.title, systemImage: destination.icon)
                    }.buttonStyle(.plain)
                }
            }
        }
        .scrollContentBackground(.hidden)
        .background(JafarPalette.backgroundSecondary)
        .navigationTitle("ЮСТИЦИЯ AI")
        .safeAreaInset(edge: .bottom) {
            HStack(spacing: JusticeSpacing.sm) {
                Circle().fill(JafarPalette.success).frame(width: 8, height: 8)
                Text("Контролируемый режим").font(JusticeTypography.caption).foregroundStyle(JafarPalette.textSecondary)
            }.padding(.horizontal).padding(.vertical, JusticeSpacing.sm)
        }
    }

    @ViewBuilder
    private func destinationView(_ destination: JusticeDestination) -> some View {
        switch destination {
        case .home: JusticeHomeView(dashboard: dashboard, onMatter: { selectedMatter = $0; selection = .matters })
        case .matters: JusticeMattersView(dashboard: dashboard, selectedMatter: $selectedMatter)
        case .settings: JusticeSettingsView()
        case .approvals: JusticeApprovalView()
        case .costs: JusticeCostView()
        case .council: JusticeCouncilView()
        case .documents: JusticeModuleBoardView(destination: .documents)
        case .evidence: JusticeModuleBoardView(destination: .evidence)
        case .timeline: JusticeModuleBoardView(destination: .timeline)
        case .contradictions: JusticeModuleBoardView(destination: .contradictions)
        case .authorities: JusticeModuleBoardView(destination: .authorities)
        case .position: JusticeModuleBoardView(destination: .position)
        case .hearing: JusticeModuleBoardView(destination: .hearing)
        case .court: JusticeCourtModeView()
        }
    }
}

private struct JusticePage<Content: View>: View {
    let title: String
    let subtitle: String
    @ViewBuilder let content: Content
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: JusticeSpacing.xl) {
                VStack(alignment: .leading, spacing: JusticeSpacing.xs) {
                    Text(title).font(JusticeTypography.display).foregroundStyle(JafarPalette.textPrimary)
                    Text(subtitle).font(JusticeTypography.callout).foregroundStyle(JafarPalette.textSecondary)
                }
                content
            }
            .frame(maxWidth: 1080, alignment: .leading)
            .padding(.horizontal, JusticeSpacing.xl)
            .padding(.vertical, JusticeSpacing.xl)
            .frame(maxWidth: .infinity, alignment: .center)
        }
        .background(JafarPalette.backgroundPrimary)
    }
}

private struct JusticeHomeView: View {
    @ObservedObject var dashboard: DashboardStore
    let onMatter: (DashboardMatter) -> Void
    private var matters: [DashboardMatter] { dashboard.snapshot.matters.isEmpty ? JusticeSamples.matters : dashboard.snapshot.matters }
    var body: some View {
        JusticePage(title: "Добрый день, адвокат", subtitle: "Командный центр: что требует вашего внимания сейчас") {
            HStack(spacing: JusticeSpacing.sm) {
                JusticePresenceView(state: dashboard.errorMessage == nil ? .calm : .control)
                VStack(alignment: .leading, spacing: JusticeSpacing.xs) {
                    Text(dashboard.errorMessage == nil ? "Юстиция готова" : "Нет соединения с ЮСТИЦИЯ AI").font(JusticeTypography.headline)
                    Text("Решение всегда остаётся за вами.").font(JusticeTypography.caption).foregroundStyle(JafarPalette.textSecondary)
                }
                Spacer()
                Label("Сегодня", systemImage: "calendar").font(JusticeTypography.caption).foregroundStyle(JafarPalette.textSecondary)
            }
            .padding(JusticeSpacing.lg).background(JafarPalette.surfaceElevated, in: RoundedRectangle(cornerRadius: JusticeRadius.large))

            priorityGrid
            section("Активные дела", "Последние изменения и ближайший следующий шаг") {
                LazyVGrid(columns: [GridItem(.adaptive(minimum: 260), spacing: JusticeSpacing.md)], spacing: JusticeSpacing.md) {
                    ForEach(matters.prefix(4)) { matter in MatterCard(matter: matter, action: { onMatter(matter) }) }
                }
            }
            section("Контроль и безопасность", "Прозрачные границы аналитики") {
                HStack(alignment: .top, spacing: JusticeSpacing.md) {
                    Image(systemName: "hand.raised.fill").foregroundStyle(JafarPalette.accentGold)
                    Text("Результат сформирован системой и требует профессиональной оценки адвоката. Действия с юридическими последствиями не выполняются без вашего подтверждения.")
                        .font(JusticeTypography.callout).foregroundStyle(JafarPalette.textSecondary)
                }.padding(JusticeSpacing.lg).jafarCard()
            }
        }
    }
    private var priorityGrid: some View {
        LazyVGrid(columns: [GridItem(.adaptive(minimum: 170), spacing: JusticeSpacing.md)], spacing: JusticeSpacing.md) {
            PriorityCard(title: "Решения", value: dashboard.snapshot.pendingApprovals, icon: "checkmark.seal.fill", color: JafarPalette.accentGold)
            PriorityCard(title: "Сроки на 7 дней", value: dashboard.snapshot.deadlinesNext7Days, icon: "calendar.badge.clock", color: JafarPalette.warning)
            PriorityCard(title: "Просрочено", value: dashboard.snapshot.overdueDeadlines, icon: "exclamationmark.triangle.fill", color: JafarPalette.danger)
            PriorityCard(title: "Сигналы", value: dashboard.snapshot.signals.count, icon: "bell.badge.fill", color: JafarPalette.accentBlue)
        }
    }
    private func section<Content: View>(_ title: String, _ subtitle: String, @ViewBuilder content: () -> Content) -> some View {
        VStack(alignment: .leading, spacing: JusticeSpacing.md) {
            VStack(alignment: .leading, spacing: JusticeSpacing.xs) { Text(title).font(JusticeTypography.title); Text(subtitle).font(JusticeTypography.caption).foregroundStyle(JafarPalette.textSecondary) }
            content()
        }
    }
}

private struct PriorityCard: View {
    let title: String; let value: Int; let icon: String; let color: Color
    var body: some View { VStack(alignment: .leading, spacing: JusticeSpacing.sm) { Image(systemName: icon).foregroundStyle(color); Text("\(value)").font(JusticeTypography.titleLarge).foregroundStyle(JafarPalette.textPrimary); Text(title).font(JusticeTypography.caption).foregroundStyle(JafarPalette.textSecondary) }.frame(maxWidth: .infinity, alignment: .leading).padding(JusticeSpacing.lg).jafarCard() }
}

private struct MatterCard: View {
    let matter: DashboardMatter; let action: () -> Void
    var body: some View {
        Button(action: action) {
            VStack(alignment: .leading, spacing: JusticeSpacing.sm) {
                HStack { Image(systemName: "briefcase.fill").foregroundStyle(JafarPalette.accentGold); Spacer(); Text(matter.status.uppercased()).font(JusticeTypography.mono).foregroundStyle(JafarPalette.success) }
                Text(matter.title).font(JusticeTypography.headline).foregroundStyle(JafarPalette.textPrimary).lineLimit(2)
                if let client = matter.clientName { Text(client).font(JusticeTypography.caption).foregroundStyle(JafarPalette.textSecondary) }
                Divider().overlay(JafarPalette.divider)
                HStack { Label(matter.nextDeadlineTitle ?? "Нет ближайшего срока", systemImage: "calendar"); Spacer(); Image(systemName: "chevron.right") }.font(JusticeTypography.caption).foregroundStyle(matter.overdueDeadlineCount > 0 ? JafarPalette.danger : JafarPalette.textSecondary)
            }.frame(maxWidth: .infinity, alignment: .leading).padding(JusticeSpacing.lg).jafarCard()
        }.buttonStyle(.plain).accessibilityLabel("Открыть дело \(matter.title)")
    }
}

private struct JusticeMattersView: View {
    @ObservedObject var dashboard: DashboardStore
    @Binding var selectedMatter: DashboardMatter?
    @State private var query = ""
    @State private var showArchived = false
    private var matters: [DashboardMatter] { (dashboard.snapshot.matters.isEmpty ? JusticeSamples.matters : dashboard.snapshot.matters).filter { query.isEmpty || $0.title.localizedCaseInsensitiveContains(query) || ($0.clientName ?? "").localizedCaseInsensitiveContains(query) } }
    var body: some View {
        JusticePage(title: "Дела", subtitle: "Рабочая карта позиций, сроков и рисков") {
            HStack { Image(systemName: "magnifyingglass"); TextField("Поиск по названию или клиенту", text: $query); Spacer(); Toggle("Архив", isOn: $showArchived).toggleStyle(.switch).font(JusticeTypography.caption) }.foregroundStyle(JafarPalette.textSecondary).padding(JusticeSpacing.md).background(JafarPalette.surface, in: RoundedRectangle(cornerRadius: JusticeRadius.small))
            if matters.isEmpty { JusticeEmptyState(title: "Нет дел", message: "Создайте первое дело, чтобы Юстиция могла систематизировать документы, сроки и доказательства.", icon: "briefcase") }
            else { LazyVGrid(columns: [GridItem(.adaptive(minimum: 280), spacing: JusticeSpacing.md)], spacing: JusticeSpacing.md) { ForEach(matters) { matter in MatterCard(matter: matter) { selectedMatter = matter } } } }
        }
    }
}

private struct JusticeModuleBoardView: View {
    let destination: JusticeDestination
    var body: some View {
        JusticePage(title: destination.title, subtitle: moduleSubtitle) {
            if destination == .contradictions { contradictionCards } else if destination == .authorities { authorityCards } else if destination == .timeline { timelineCards } else { genericCards }
        }
    }
    private var moduleSubtitle: String { switch destination { case .documents: "Кандидаты, источники и анализ без автоматического сохранения"; case .evidence: "Связи между источниками, фактами и правовыми вопросами"; case .timeline: "Профессиональная chronology с точностью дат и provenance"; case .contradictions: "Расхождения, требующие проверки адвокатом"; case .authorities: "Официальные позиции и discovery-источники с маркировкой статуса"; case .position: "Версии защиты и оппонента, собранные в проверяемый draft"; case .hearing: "Цель заседания, тезисы, вопросы и процессуальный checklist"; default: "Рабочее пространство по делу" } }
    private var genericCards: some View { VStack(alignment: .leading, spacing: JusticeSpacing.md) { ForEach(0..<4, id: \.self) { index in HStack(spacing: JusticeSpacing.md) { Image(systemName: destination.icon).foregroundStyle(index == 0 ? JafarPalette.accentGold : JafarPalette.accentBlue); VStack(alignment: .leading, spacing: JusticeSpacing.xs) { Text(sampleTitle(index)).font(JusticeTypography.headline); Text("Кандидат · источник и уверенность доступны для проверки").font(JusticeTypography.caption).foregroundStyle(JafarPalette.textSecondary) }; Spacer(); Image(systemName: "chevron.right").foregroundStyle(JafarPalette.textMuted) }.padding(JusticeSpacing.lg).jafarCard() }; JusticeSafetyNotice(text: "Сведения на этом экране являются кандидатами и не меняют позицию дела автоматически.") } }
    private var contradictionCards: some View { VStack(spacing: JusticeSpacing.md) { ForEach([("Дата события", "Протокол от 12.03.2026", "Письмо от 14.03.2026"), ("Сумма", "1 200 000 ₽", "980 000 ₽")], id: \.0) { item in VStack(alignment: .leading, spacing: JusticeSpacing.sm) { Label(item.0, systemImage: "exclamationmark.triangle.fill").foregroundStyle(JafarPalette.warning); Text(item.1).font(JusticeTypography.callout); Text(item.2).font(JusticeTypography.callout).foregroundStyle(JafarPalette.textSecondary); Text("Предложенная проверка: сопоставить первоисточники").font(JusticeTypography.caption).foregroundStyle(JafarPalette.textMuted) }.padding(JusticeSpacing.lg).jafarCard() }; JusticeSafetyNotice(text: "Добавление в правовую позицию доступно только после review адвоката.") } }
    private var authorityCards: some View { VStack(spacing: JusticeSpacing.md) { ForEach([("Верховный Суд РФ", "Определение № А00-00000/2026", "Официальный источник"), ("Sudact", "Подборка практики по вопросу", "Discovery source · требует проверки")], id: \.0) { item in HStack { Image(systemName: "building.columns.fill").foregroundStyle(JafarPalette.accentGold); VStack(alignment: .leading) { Text(item.0).font(JusticeTypography.headline); Text(item.1).font(JusticeTypography.callout); Text(item.2).font(JusticeTypography.caption).foregroundStyle(JafarPalette.textSecondary) }; Spacer() }.padding(JusticeSpacing.lg).jafarCard() } } }
    private var timelineCards: some View { VStack(alignment: .leading, spacing: JusticeSpacing.md) { ForEach([("12.03.2026", "Процессуальное событие", "Протокол заседания"), ("14.03.2026", "Документ", "Письмо контрагента"), ("—", "Дата требует уточнения", "Источник не подтверждён")], id: \.0) { item in HStack(alignment: .top, spacing: JusticeSpacing.md) { Text(item.0).font(JusticeTypography.mono).foregroundStyle(JafarPalette.accentGold).frame(width: 90, alignment: .leading); VStack(alignment: .leading) { Text(item.1).font(JusticeTypography.headline); Text(item.2).font(JusticeTypography.caption).foregroundStyle(JafarPalette.textSecondary) } } .padding(JusticeSpacing.lg).jafarCard() } } }
    private func sampleTitle(_ index: Int) -> String { switch destination { case .documents: ["Договор поставки.pdf", "Переписка сторон.txt", "Протокол заседания.pdf", "Экспертиза.docx"][index]; case .evidence: ["Подписанный договор", "Платёжное поручение", "Показания свидетеля", "Фотоматериал"][index]; case .position: ["Версия защиты", "Факты за позицию", "Слабые места", "Альтернативная версия"][index]; case .hearing: ["Цель заседания", "Основные тезисы", "Вопросы суду", "Документы с собой"][index]; default: "Рабочий элемент \(index + 1)" } }
}

private struct JusticeCouncilView: View {
    var body: some View { JusticePage(title: "Совет моделей", subtitle: "Независимые варианты анализа и явные разногласия") { HStack(spacing: JusticeSpacing.md) { ForEach(["OpenAI", "Gemini", "DeepSeek", "Qwen", "Kimi"], id: \.self) { provider in VStack(alignment: .leading, spacing: JusticeSpacing.sm) { Text(provider).font(JusticeTypography.headline); Text("Ожидает анализа").font(JusticeTypography.caption).foregroundStyle(JafarPalette.textSecondary); ProgressView(value: provider == "OpenAI" ? 0.72 : 0.48).tint(JafarPalette.accentGold) }.frame(maxWidth: .infinity, alignment: .leading).padding(JusticeSpacing.md).jafarCard() } }; VStack(alignment: .leading, spacing: JusticeSpacing.md) { Text("Итоговая сводка").font(JusticeTypography.title); Text("В демо-режиме результаты заменены синтетическими данными. Реальный анализ появляется только после явного действия адвоката.").font(JusticeTypography.body).foregroundStyle(JafarPalette.textSecondary); JusticeSafetyNotice(text: "Совет моделей формирует варианты анализа. Итоговую позицию определяет адвокат.") }.padding(JusticeSpacing.lg).jafarCard(); HStack { Text("Совпадения  ·  3"); Text("Разногласия  ·  2"); Text("Проверить  ·  4") }.font(JusticeTypography.callout).foregroundStyle(JafarPalette.accentGold) } }
}

private struct JusticeApprovalView: View {
    var body: some View { JusticePage(title: "Решения", subtitle: "Только явно подтверждённые действия адвоката") { ForEach(["Подготовить проект ходатайства", "Обновить candidate-факт"], id: \.self) { title in VStack(alignment: .leading, spacing: JusticeSpacing.md) { HStack { Image(systemName: "checkmark.seal.fill").foregroundStyle(JafarPalette.accentGold); Text(title).font(JusticeTypography.headline); Spacer(); Text("Ожидает решения").font(JusticeTypography.caption).foregroundStyle(JafarPalette.warning) }; Text("Действие не будет выполнено без вашего подтверждения.").font(JusticeTypography.caption).foregroundStyle(JafarPalette.textSecondary); HStack { Button("Одобрить") {}.buttonStyle(.borderedProminent).tint(JafarPalette.accentGold); Button("Отклонить") {}.buttonStyle(.bordered); Spacer(); Text("Требует проверки").font(JusticeTypography.caption).foregroundStyle(JafarPalette.textMuted) } }.padding(JusticeSpacing.lg).jafarCard() }; JusticeSafetyNotice(text: "Перед одобрением потребуется Face ID, Touch ID или код-пароль устройства. Само одобрение не выполняет внешнее действие автоматически.") } }
}

private struct JusticeCostView: View {
    var body: some View { JusticePage(title: "Использование AI", subtitle: "Прозрачные расходы без персональных данных") { HStack(spacing: JusticeSpacing.md) { PriorityCard(title: "Сегодня", value: 12, icon: "sun.max.fill", color: JafarPalette.accentGold); PriorityCard(title: "Месяц", value: 38, icon: "calendar", color: JafarPalette.accentBlue); PriorityCard(title: "Reserved", value: 4, icon: "lock.fill", color: JafarPalette.warning) }; VStack(alignment: .leading, spacing: JusticeSpacing.md) { Text("Лимит месяца").font(JusticeTypography.headline); ProgressView(value: 0.38).tint(JafarPalette.accentGold); Text("38% · предупреждения на 50 / 75 / 90 / 100%").font(JusticeTypography.caption).foregroundStyle(JafarPalette.textSecondary) }.padding(JusticeSpacing.lg).jafarCard(); ForEach(["OpenAI · gpt-5.6", "Qwen · qwen3.8-max", "Kimi · kimi-k3"], id: \.self) { Text($0).font(JusticeTypography.callout).padding(JusticeSpacing.md).frame(maxWidth: .infinity, alignment: .leading).background(JafarPalette.surface, in: RoundedRectangle(cornerRadius: JusticeRadius.small)) } } }
}

private struct JusticeSettingsView: View {
    var body: some View { JusticePage(title: "Настройки", subtitle: "Среда, безопасность и предпочтения ЮСТИЦИЯ AI") { settingsSection("Подключение", icon: "network") { setting("Среда", "Private Beta"); setting("Состояние backend", "Проверяется при открытии") }; settingsSection("AI и конфиденциальность", icon: "lock.shield.fill") { setting("Провайдеры", "Только доверенные"); setting("Стоимость", "Лимиты включены") }; settingsSection("Безопасность", icon: "faceid") { setting("Подтверждение решений", "Face ID / Touch ID / код-пароль"); setting("Хранилище токена", "Защищённая связка ключей") }; settingsSection("О приложении", icon: "info.circle") { setting("ЮСТИЦИЯ AI", "Интеллектуальная система адвоката"); setting("Версия", "0.9.12") } } }
    private func settingsSection<Content: View>(_ title: String, icon: String, @ViewBuilder content: () -> Content) -> some View { VStack(alignment: .leading, spacing: JusticeSpacing.md) { Label(title, systemImage: icon).font(JusticeTypography.title); VStack(spacing: 0) { content() }.padding(JusticeSpacing.md).jafarCard() } }
    private func setting(_ key: String, _ value: String) -> some View { HStack { Text(key).font(JusticeTypography.callout); Spacer(); Text(value).font(JusticeTypography.caption).foregroundStyle(JafarPalette.textSecondary) }.padding(.vertical, JusticeSpacing.sm) }
}

private struct JusticeCourtModeView: View { var body: some View { JusticePage(title: "Court Mode", subtitle: "Минимум отвлечений. Только то, что нужно в заседании") { ForEach(["Ключевые тезисы", "Вопросы суду", "Objections", "Документы", "Хронология", "Быстрый поиск"], id: \.self) { item in Label(item, systemImage: "chevron.right").font(JusticeTypography.title).padding(JusticeSpacing.lg).frame(maxWidth: .infinity, alignment: .leading).background(JafarPalette.surface, in: RoundedRectangle(cornerRadius: JusticeRadius.small)) } } } }

private struct JusticeSafetyNotice: View { let text: String; var body: some View { Label(text, systemImage: "hand.raised.fill").font(JusticeTypography.caption).foregroundStyle(JafarPalette.textSecondary).padding(JusticeSpacing.md).background(JafarPalette.accentGold.opacity(0.10), in: RoundedRectangle(cornerRadius: JusticeRadius.small)) } }
private struct JusticeEmptyState: View { let title: String; let message: String; let icon: String; var body: some View { VStack(spacing: JusticeSpacing.md) { Image(systemName: icon).font(.system(size: 38)).foregroundStyle(JafarPalette.accentGold); Text(title).font(JusticeTypography.title); Text(message).font(JusticeTypography.body).foregroundStyle(JafarPalette.textSecondary).multilineTextAlignment(.center) }.frame(maxWidth: .infinity).padding(JusticeSpacing.xxl).jafarCard() } }

private enum JusticeSamples {
    static let matters = [
        DashboardMatter(id: "demo-1", title: "ООО «Альфа» — поставка", status: "active", matterType: "Арбитраж", clientName: "ООО «Альфа»", caseNumber: "А00-00000/2026", deadlineCount: 3, overdueDeadlineCount: 0, nextDeadlineTitle: "Отзыв на иск", nextDeadlineDate: "20.04.2026"),
        DashboardMatter(id: "demo-2", title: "Иванов И.И. — защита", status: "active", matterType: "Уголовное", clientName: "Иванов И.И.", caseNumber: "00-000/2026", deadlineCount: 2, overdueDeadlineCount: 1, nextDeadlineTitle: "Заседание", nextDeadlineDate: "18.04.2026")
    ]
}
