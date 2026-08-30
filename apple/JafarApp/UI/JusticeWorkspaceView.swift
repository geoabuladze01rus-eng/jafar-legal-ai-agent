import SwiftUI

private enum JusticeDestination: String, CaseIterable, Identifiable {
    case home, matters, calendar, documents, mail, radar, practice, drafts, voice, analytics, library, counterparties, evidence, timeline, contradictions, authorities
    case council, position, hearing, court, approvals, costs, settings

    var id: String { rawValue }
    var title: String {
        switch self {
        case .home: "Главная"; case .matters: "Дела"; case .calendar: "Календарь"; case .documents: "Документы"; case .mail: "Почта"; case .radar: "Правовой радар"; case .practice: "Практика"; case .drafts: "Черновики"; case .voice: "Голосовые материалы"; case .analytics: "Аналитика"; case .library: "Библиотека норм"; case .counterparties: "Проверка контрагентов"
        case .evidence: "Доказательства"; case .timeline: "Хронология"
        case .contradictions: "Противоречия"; case .authorities: "Судебная практика"
        case .council: "Совет моделей"; case .position: "Правовая позиция"
        case .hearing: "Подготовка к заседанию"; case .court: "Режим суда"
        case .approvals: "Решения"; case .costs: "Использование AI"; case .settings: "Настройки"
        }
    }
    var icon: String {
        switch self {
        case .home: "house.fill"; case .matters: "briefcase.fill"; case .calendar: "calendar"; case .documents: "doc.text.fill"; case .mail: "envelope"; case .radar: "dot.radiowaves.left.and.right"; case .practice: "books.vertical"; case .drafts: "square.and.pencil"; case .voice: "waveform"; case .analytics: "chart.bar.xaxis"; case .library: "books.vertical.fill"; case .counterparties: "person.crop.rectangle"
        case .evidence: "link"; case .timeline: "clock.arrow.circlepath"
        case .contradictions: "exclamationmark.triangle.fill"; case .authorities: "building.columns.fill"
        case .council: "person.3.fill"; case .position: "text.book.closed.fill"
        case .hearing: "checklist"; case .court: "scale.3d"; case .approvals: "checkmark.seal.fill"
        case .costs: "chart.bar.xaxis"; case .settings: "gearshape.fill"
        }
    }
    static var primary: [JusticeDestination] { [.home, .matters, .calendar, .documents, .mail, .radar, .practice, .drafts, .voice, .analytics, .library, .counterparties, .settings] }
}

struct JusticeWorkspaceView: View {
    @ObservedObject var dashboard: DashboardStore
    @Environment(\.horizontalSizeClass) private var sizeClass
    @State private var selection: JusticeDestination = .home
    @State private var selectedMatter: DashboardMatter?
    @State private var searchText = ""
    @State private var hoveredDestination: JusticeDestination?
    @AppStorage("justice.demo_mode") private var demoMode = false

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
                    Button { withAnimation(JafarMotion.normal) { selection = destination } } label: {
                        Label(destination.title, systemImage: destination.icon)
                            .frame(maxWidth: .infinity, alignment: .leading)
                    }
                    .buttonStyle(.plain)
                    .padding(.vertical, 3)
                    .padding(.horizontal, 8)
                    .background(selection == destination ? JafarPalette.accent.opacity(0.18) : .clear, in: RoundedRectangle(cornerRadius: 7))
                    .background(hoveredDestination == destination ? JafarPalette.accent.opacity(0.10) : .clear, in: RoundedRectangle(cornerRadius: 7))
                    .overlay(alignment: .leading) { Capsule().fill(selection == destination || hoveredDestination == destination ? JafarPalette.accentGold : .clear).frame(width: 2, height: 20) }
                    .foregroundStyle(selection == destination || hoveredDestination == destination ? JafarPalette.accentGold : JafarPalette.textSecondary)
                    .onHover { inside in withAnimation(JafarMotion.fast) { hoveredDestination = inside ? destination : nil } }
                    .animation(JafarMotion.normal, value: selection)
                }
            } header: {
                VStack(alignment: .leading, spacing: 4) {
                    HStack(spacing: 8) { Image(systemName: "scalemass.fill").foregroundStyle(JafarPalette.accentGold); Text("JAFAR AI").font(JusticeTypography.title).foregroundStyle(JafarPalette.textPrimary) }
                    Text("Юридический помощник адвоката").font(JusticeTypography.caption).foregroundStyle(JafarPalette.textSecondary)
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
        .navigationTitle("JAFAR AI")
        .safeAreaInset(edge: .bottom) {
            HStack(spacing: JusticeSpacing.sm) {
                Circle().fill(JafarPalette.success).frame(width: 8, height: 8)
                VStack(alignment: .leading, spacing: 2) { Text("Система активна").font(JusticeTypography.caption).foregroundStyle(JafarPalette.textPrimary); Text("Все сервисы работают").font(.caption2).foregroundStyle(JafarPalette.textMuted) }
            }.padding(.horizontal).padding(.vertical, JusticeSpacing.sm)
        }
    }

    @ViewBuilder
    private func destinationView(_ destination: JusticeDestination) -> some View {
        switch destination {
        case .home: JusticeHomeView(dashboard: dashboard, demoMode: demoMode, onMatter: { selectedMatter = $0; selection = .matters })
        case .matters: JusticeMattersView(dashboard: dashboard, demoMode: demoMode, selectedMatter: $selectedMatter)
        case .settings: JusticeSettingsView(demoMode: $demoMode)
        case .approvals: JusticeApprovalView()
        case .costs: JusticeCostView()
        case .council: JusticeCouncilView()
        case .calendar, .mail, .radar, .practice, .drafts, .voice, .analytics, .library, .counterparties: JusticeModuleBoardView(destination: destination)
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
        .background {
            ZStack {
                LinearGradient(colors: [Color(red: 3 / 255, green: 7 / 255, blue: 13 / 255), JafarPalette.backgroundPrimary], startPoint: .top, endPoint: .bottom)
                RadialGradient(colors: [JafarPalette.accent.opacity(0.12), .clear], center: .center, startRadius: 20, endRadius: 620)
                RadialGradient(colors: [JafarPalette.accentBlue.opacity(0.12), .clear], center: .topLeading, startRadius: 10, endRadius: 500)
            }.ignoresSafeArea()
        }
    }
}

private struct JusticeHomeView: View {
    @ObservedObject var dashboard: DashboardStore
    let demoMode: Bool
    let onMatter: (DashboardMatter) -> Void
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var heroBreath = false
    @State private var heroRingRotation = false
    @State private var analyzingSweep = false
    @State private var listening = false
    @State private var quickAction: String?
    private var matters: [DashboardMatter] { demoMode ? JusticeSamples.matters : dashboard.snapshot.matters }
    var body: some View {
        JusticePage(title: "Доброе утро, Иван Иванович", subtitle: "JAFAR AI готов служить вашей практике") {
            HStack(spacing: 8) { HStack { Image(systemName: "magnifyingglass"); Text("Поиск по делам и документам..."); Spacer(); Text("⌘K").font(JusticeTypography.mono) }.font(JusticeTypography.caption).foregroundStyle(JafarPalette.textMuted).padding(9).background(JafarPalette.surface, in: RoundedRectangle(cornerRadius: 7)).overlay(RoundedRectangle(cornerRadius: 7).stroke(JafarPalette.divider)); Button { } label: { Image(systemName: "bell").frame(width: 28, height: 28) }.buttonStyle(.plain).foregroundStyle(JafarPalette.accentGold); Button { } label: { Image(systemName: "gearshape").frame(width: 28, height: 28) }.buttonStyle(.plain).foregroundStyle(JafarPalette.textSecondary); Button("+ Создать") { }.buttonStyle(.borderedProminent).tint(JafarPalette.accentGold) }
            HStack(alignment: .top, spacing: JusticeSpacing.md) {
                focusCard.frame(width: 220)
                VStack(alignment: .leading, spacing: JusticeSpacing.md) {
                    heroCard
                    commandBar
                    matterActivityRow
                    lowerModules
                    footerBar
                }.frame(maxWidth: .infinity)
                verticalRightRail.frame(width: 260)
            }
        }
    }
    private var verticalRightRail: some View { VStack(alignment: .leading, spacing: JusticeSpacing.md) { intelligenceCard; rightRailCard(title: "ЗАДАЧИ И СРОКИ", icon: "calendar.badge.clock", items: ["Отзыв на иск · 3 дня", "Проверить источник · сегодня", "Подготовить вопросы · 5 дней", "Сверить приложения · 7 дней"]); rightRailCard(title: "БЛИЖАЙШИЕ ЗАСЕДАНИЯ", icon: "building.columns", items: ["18 апреля · 10:30", "А00-00000/2026", "Арбитражный суд"]); quoteCard } }
    private func rightRailCard(title: String, icon: String, items: [String]) -> some View { VStack(alignment: .leading, spacing: 9) { Label(title, systemImage: icon).font(JusticeTypography.caption).foregroundStyle(JafarPalette.accentGold); ForEach(items, id: \.self) { Text($0).font(JusticeTypography.caption).foregroundStyle(JafarPalette.textSecondary).lineLimit(2) } }.frame(maxWidth: .infinity, alignment: .leading).padding(14).jafarCard() }
    private var quoteCard: some View { VStack(alignment: .leading, spacing: 8) { Text("«Право — это искусство добра и справедливости»").font(JusticeTypography.callout).italic().foregroundStyle(JafarPalette.textPrimary); Text("— Цицерон").font(.caption2).foregroundStyle(JafarPalette.textMuted) }.frame(maxWidth: .infinity, alignment: .leading).padding(14).jafarCard() }
    private var lowerModules: some View { HStack(alignment: .top, spacing: JusticeSpacing.md) { VStack(alignment: .leading, spacing: 8) { Label("ПРАВОВОЙ РАДАР", systemImage: "dot.radiowaves.left.and.right").foregroundStyle(JafarPalette.accentGold); Text("12 обновлений").font(JusticeTypography.title); Text("ВС РФ · Пленум · изменения ГПК/УПК").font(JusticeTypography.caption).foregroundStyle(JafarPalette.textSecondary) }.frame(maxWidth: .infinity, alignment: .leading).padding(16).jafarCard(); VStack(alignment: .leading, spacing: 8) { Label("AI-АНАЛИТИКА", systemImage: "chart.pie.fill").foregroundStyle(JafarPalette.accentGold); HStack { ZStack { Circle().stroke(JafarPalette.divider, lineWidth: 8); Circle().trim(from: 0, to: 0.57).stroke(JafarPalette.accentGold, style: StrokeStyle(lineWidth: 8, lineCap: .round)).rotationEffect(.degrees(-90)); Text("57%").font(JusticeTypography.headline) }.frame(width: 56, height: 56); Text("Средний риск").font(JusticeTypography.callout) } }.frame(maxWidth: .infinity, alignment: .leading).padding(16).jafarCard(); VStack(alignment: .leading, spacing: 8) { Label("ГОЛОСОВЫЕ МАТЕРИАЛЫ", systemImage: "waveform").foregroundStyle(JafarPalette.accentGold); HStack(alignment: .bottom, spacing: 3) { ForEach(0..<18, id: \.self) { index in Capsule().fill(JafarPalette.accent.opacity(0.7)).frame(width: 3, height: CGFloat(8 + (index % 5) * 5)) } }; Text("3 записи · 42 мин").font(JusticeTypography.caption).foregroundStyle(JafarPalette.textSecondary) }.frame(maxWidth: .infinity, alignment: .leading).padding(16).jafarCard() } }
    private var focusCard: some View { VStack(alignment: .leading, spacing: 10) { Text("ФОКУС ДНЯ").font(JusticeTypography.title).foregroundStyle(JafarPalette.accentGold); focusRow("Требуют внимания", 3, "exclamationmark.triangle"); focusRow("Новые письма", 1, "envelope.fill"); focusRow("Новые документы", 2, "doc.text"); focusRow("Заседание завтра", 10, "calendar") }.padding(13).jafarCard() }
    private func focusRow(_ title: String, _ value: Int, _ icon: String) -> some View { HStack(alignment: .top) { Image(systemName: icon).foregroundStyle(JafarPalette.accentGold); VStack(alignment: .leading) { Text(title).font(JusticeTypography.caption).foregroundStyle(JafarPalette.textSecondary); Text("\(value)").font(JusticeTypography.headline).foregroundStyle(JafarPalette.textPrimary) } } }
    private var heroCard: some View { ZStack(alignment: .bottomLeading) { Circle().fill(JafarPalette.goldGlow.opacity(0.18)).blur(radius: 24).scaleEffect(heroBreath ? 1.08 : 0.90); Circle().stroke(JafarPalette.accent.opacity(0.45), lineWidth: 1).frame(width: 190, height: 190).rotationEffect(.degrees(heroRingRotation ? 360 : 0)); Circle().stroke(JafarPalette.goldHighlight.opacity(0.18), lineWidth: 1).frame(width: 230, height: 230); Image("JusticeHero").resizable().scaledToFill().frame(maxWidth: .infinity, maxHeight: 210).clipped().opacity(0.95); VStack(alignment: .leading, spacing: 2) { Text("ЮСТИЦИЯ").font(JusticeTypography.titleLarge).foregroundStyle(JafarPalette.textPrimary); Text("Статус: \(dashboard.errorMessage == nil ? "Система активна" : "Требуется решение")").font(JusticeTypography.caption).foregroundStyle(JafarPalette.accentGold) }.padding(14) }.frame(height: 215).overlay(RoundedRectangle(cornerRadius: 8).stroke(JafarPalette.accent.opacity(0.32))).onAppear { guard !reduceMotion else { return }; withAnimation(JafarMotion.ambient) { heroBreath = true }; withAnimation(.linear(duration: 18).repeatForever(autoreverses: false)) { heroRingRotation = true }; withAnimation(.easeInOut(duration: 3).repeatForever(autoreverses: true)) { analyzingSweep = true } } }
    private var intelligenceCard: some View { VStack(alignment: .leading, spacing: 9) { ZStack { Circle().stroke(JafarPalette.accent.opacity(0.3), lineWidth: 1); Circle().trim(from: 0.08, to: 0.72).stroke(JafarPalette.accentGold, style: StrokeStyle(lineWidth: 2, lineCap: .round)).rotationEffect(.degrees(analyzingSweep ? 360 : 0)); Image(systemName: "scalemass.fill").foregroundStyle(JafarPalette.accentGold) }.frame(width: 48, height: 48); Text("JAFAR AI").font(JusticeTypography.title).foregroundStyle(JafarPalette.accentGold); Text("Анализирует ваши дела").font(JusticeTypography.headline); ForEach(["Правовой анализ", "Процессуальные риски", "Стратегию защиты", "Черновики документов"], id: \.self) { item in Label(item, systemImage: "checkmark").font(JusticeTypography.caption).foregroundStyle(JafarPalette.textSecondary) }; Button("Начать диалог") {}.buttonStyle(.borderedProminent).tint(JafarPalette.accentGold) }.padding(13).jafarCard() }
    private var commandBar: some View { VStack(alignment: .leading, spacing: 7) { HStack { Image(systemName: "scalemass.fill").foregroundStyle(JafarPalette.accentGold); Text("Спросите Джафара...").font(JusticeTypography.headline).foregroundStyle(JafarPalette.textMuted); Spacer(); Button { withAnimation(JafarMotion.normal) { listening.toggle() } } label: { ZStack { Circle().fill(listening ? JafarPalette.accentGold.opacity(0.28) : JafarPalette.accent.opacity(0.12)); Image(systemName: "mic.fill").foregroundStyle(JafarPalette.accentGold); if listening && !reduceMotion { Circle().stroke(JafarPalette.accentGold.opacity(0.7), lineWidth: 1).scaleEffect(1.25).opacity(0.2) } }.frame(width: 28, height: 28) }.buttonStyle(.plain) }.padding(10).background(JafarPalette.surface, in: Capsule()).overlay(Capsule().stroke(listening ? JafarPalette.accentGold : JafarPalette.accent.opacity(0.35), lineWidth: listening ? 1.5 : 1)); HStack(spacing: 6) { ForEach(["Что требует моего внимания?", "Разбери последнее письмо", "Что нового по делу Павлика?", "Подготовь правовую позицию"], id: \.self) { action in Button { withAnimation(JafarMotion.fast) { quickAction = action } } label: { Text(action).font(JusticeTypography.caption).foregroundStyle(quickAction == action ? JafarPalette.textPrimary : JafarPalette.accentGold).padding(.horizontal, 9).padding(.vertical, 5).background(quickAction == action ? JafarPalette.accent.opacity(0.28) : .clear, in: Capsule()).overlay(Capsule().stroke(JafarPalette.accent.opacity(quickAction == action ? 0.85 : 0.45), lineWidth: quickAction == action ? 1.5 : 1)) }.buttonStyle(.plain).scaleEffect(quickAction == action ? 0.98 : 1) } } } }
    private var matterActivityRow: some View { HStack(alignment: .top, spacing: JusticeSpacing.md) { section("МОИ ДЕЛА", "Последние изменения и ближайший следующий шаг") { LazyVGrid(columns: [GridItem(.adaptive(minimum: 180), spacing: JusticeSpacing.sm)], spacing: JusticeSpacing.sm) { ForEach(matters.prefix(4)) { matter in MatterCard(matter: matter, action: { onMatter(matter) }) } } }.frame(maxWidth: .infinity); activityCard.frame(width: 210) } }
    private var activityCard: some View { VStack(alignment: .leading, spacing: 10) { Text("АКТИВНОСТЬ ДЖАФАРА").font(JusticeTypography.caption).foregroundStyle(JafarPalette.accentGold); ForEach([("Проанализирован документ", "10 мин"), ("Найден процессуальный риск", "1 ч"), ("Подготовлен черновик", "вчера"), ("Обновлена позиция", "вчера")], id: \.0) { event in HStack(alignment: .top) { Image(systemName: "checkmark.circle").foregroundStyle(JafarPalette.accentGold); VStack(alignment: .leading, spacing: 2) { Text(event.0).font(.caption2); Text(event.1).font(.caption2).foregroundStyle(JafarPalette.textMuted) } } } }.padding(13).jafarCard() }
    private var footerBar: some View { HStack(spacing: 14) { Label("Шифрование: активно", systemImage: "lock.fill"); Label("Резервное копирование: сегодня, 03:00", systemImage: "externaldrive.fill"); Label("Синхронизация: активно", systemImage: "arrow.triangle.2.circlepath"); Spacer(); Text("ЮСТИЦИЯ AI защищает ваши данные и помогает управлять делами").italic() }.font(.caption2).foregroundStyle(JafarPalette.textMuted).padding(.vertical, 6) }
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
    let demoMode: Bool
    @Binding var selectedMatter: DashboardMatter?
    @State private var query = ""
    @State private var showArchived = false
    private var matters: [DashboardMatter] { (demoMode ? JusticeSamples.matters : dashboard.snapshot.matters).filter { query.isEmpty || $0.title.localizedCaseInsensitiveContains(query) || ($0.clientName ?? "").localizedCaseInsensitiveContains(query) } }
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
    @Binding var demoMode: Bool
    var body: some View { JusticePage(title: "Настройки", subtitle: "Среда, безопасность и предпочтения JAFAR AI") { settingsSection("Подключение", icon: "network") { setting("Среда", "Private Beta"); setting("Состояние backend", "Проверяется при открытии") }; settingsSection("Демо и данные", icon: "theatermasks.fill") { Toggle("Демонстрационный режим", isOn: $demoMode).tint(JafarPalette.accentGold); Text("Синтетические дела изолированы от live backend и не могут вызвать одобрение или внешнее действие.").font(JusticeTypography.caption).foregroundStyle(JafarPalette.textSecondary) }; settingsSection("AI и конфиденциальность", icon: "lock.shield.fill") { setting("Провайдеры", "Только доверенные"); setting("Стоимость", "Лимиты включены") }; settingsSection("Безопасность", icon: "faceid") { setting("Подтверждение решений", "Face ID / Touch ID / код-пароль"); setting("Хранилище токена", "Защищённая связка ключей") }; settingsSection("О приложении", icon: "info.circle") { setting("JAFAR AI", "Юридический помощник адвоката"); setting("Версия", "0.9.12") } } }
    private func settingsSection<Content: View>(_ title: String, icon: String, @ViewBuilder content: () -> Content) -> some View { VStack(alignment: .leading, spacing: JusticeSpacing.md) { Label(title, systemImage: icon).font(JusticeTypography.title); VStack(spacing: 0) { content() }.padding(JusticeSpacing.md).jafarCard() } }
    private func setting(_ key: String, _ value: String) -> some View { HStack { Text(key).font(JusticeTypography.callout); Spacer(); Text(value).font(JusticeTypography.caption).foregroundStyle(JafarPalette.textSecondary) }.padding(.vertical, JusticeSpacing.sm) }
}

private struct JusticeCourtModeView: View { var body: some View { JusticePage(title: "Режим суда", subtitle: "Минимум отвлечений. Только то, что нужно в заседании") { ForEach(["Ключевые тезисы", "Вопросы суду", "Objections", "Документы", "Хронология", "Быстрый поиск"], id: \.self) { item in Label(item, systemImage: "chevron.right").font(JusticeTypography.title).padding(JusticeSpacing.lg).frame(maxWidth: .infinity, alignment: .leading).background(JafarPalette.surface, in: RoundedRectangle(cornerRadius: JusticeRadius.small)) } } } }

private struct JusticeSafetyNotice: View { let text: String; var body: some View { Label(text, systemImage: "hand.raised.fill").font(JusticeTypography.caption).foregroundStyle(JafarPalette.textSecondary).padding(JusticeSpacing.md).background(JafarPalette.accentGold.opacity(0.10), in: RoundedRectangle(cornerRadius: JusticeRadius.small)) } }
private struct JusticeEmptyState: View { let title: String; let message: String; let icon: String; var body: some View { VStack(spacing: JusticeSpacing.md) { Image(systemName: icon).font(.system(size: 38)).foregroundStyle(JafarPalette.accentGold); Text(title).font(JusticeTypography.title); Text(message).font(JusticeTypography.body).foregroundStyle(JafarPalette.textSecondary).multilineTextAlignment(.center) }.frame(maxWidth: .infinity).padding(JusticeSpacing.xxl).jafarCard() } }

private enum JusticeSamples {
    static let matters = [
        DashboardMatter(id: "demo-1", title: "ООО «Альфа» — поставка", status: "active", matterType: "Арбитраж", clientName: "ООО «Альфа»", caseNumber: "А00-00000/2026", deadlineCount: 3, overdueDeadlineCount: 0, nextDeadlineTitle: "Отзыв на иск", nextDeadlineDate: "20.04.2026"),
        DashboardMatter(id: "demo-2", title: "Иванов И.И. — защита", status: "active", matterType: "Уголовное", clientName: "Иванов И.И.", caseNumber: "00-000/2026", deadlineCount: 2, overdueDeadlineCount: 1, nextDeadlineTitle: "Заседание", nextDeadlineDate: "18.04.2026")
    ]
}
