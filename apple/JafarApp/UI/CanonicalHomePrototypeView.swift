import SwiftUI

private struct CanonicalMatter: Identifiable {
    let id: String
    let source: DashboardMatter?
    let client: String
    let number: String
    let priority: String
    let progress: Double?
    let action: String
    let deadline: String
    let meta: String
}

private struct CanonicalActivity: Identifiable {
    let id: String
    let title: String
    let matter: String
    let timestamp: String
}

private struct CanonicalRailRow: Identifiable {
    let id: String
    let date: String
    let title: String
    let matter: String
    let urgency: String
}

private struct CanonicalPanel<Content: View>: View {
    let glow: Color?
    @ViewBuilder let content: Content

    init(glow: Color? = nil, @ViewBuilder content: () -> Content) {
        self.glow = glow
        self.content = content()
    }

    var body: some View {
        content
            .padding(12)
            .background {
                RoundedRectangle(cornerRadius: 8, style: .continuous)
                    .fill(LinearGradient(colors: [JafarPalette.surfaceElevated, JafarPalette.card], startPoint: .topLeading, endPoint: .bottomTrailing))
                    .overlay(RoundedRectangle(cornerRadius: 8).stroke(JafarPalette.accent.opacity(0.34), lineWidth: 1))
                    .overlay(alignment: .top) { Rectangle().fill(Color.white.opacity(0.10)).frame(height: 1).padding(.horizontal, 10) }
                    .shadow(color: .black.opacity(0.48), radius: 14, y: 7)
                    .overlay { if let glow { RoundedRectangle(cornerRadius: 8).fill(glow.opacity(0.07)) } }
            }
    }
}

private struct CanonicalIntelligenceEmblem: View {
    let isAnalyzing: Bool
    let isListening: Bool
    let hasControlFocus: Bool
    let breathing: Bool
    let orbiting: Bool
    let sweeping: Bool
    let reduceMotion: Bool

    private var emphasis: Color {
        hasControlFocus ? JafarPalette.goldHighlight : JafarPalette.accentGold
    }

    var body: some View {
        ZStack {
            Circle()
                .fill(
                    RadialGradient(
                        colors: [emphasis.opacity(isAnalyzing ? 0.24 : 0.16), JafarPalette.accentBlue.opacity(0.10), .clear],
                        center: .center,
                        startRadius: 2,
                        endRadius: 34
                    )
                )
                .scaleEffect(breathing ? 1.10 : 0.90)

            Circle()
                .stroke(JafarPalette.accentBlue.opacity(0.42), lineWidth: 0.7)
                .padding(2)

            Circle()
                .trim(from: 0.07, to: 0.68)
                .stroke(emphasis, style: StrokeStyle(lineWidth: 1.5, lineCap: .round))
                .padding(5)
                .rotationEffect(.degrees(orbiting ? 360 : 0))

            if isAnalyzing {
                Circle()
                    .trim(from: 0.42, to: 0.92)
                    .stroke(JafarPalette.accentBlue.opacity(0.9), style: StrokeStyle(lineWidth: 1, lineCap: .round))
                    .padding(8)
                    .rotationEffect(.degrees(orbiting ? -360 : 0))
            }

            neuralGlyph
        }
        .frame(width: 52, height: 52)
        .accessibilityLabel("Интеллектуальный модуль JAFAR AI")
    }

    private var neuralGlyph: some View {
        ZStack {
            Image(systemName: "brain.head.profile")
                .font(.system(size: 25, weight: .medium))
                .foregroundStyle(emphasis)
                .shadow(color: emphasis.opacity(0.62), radius: 5)

            if isAnalyzing {
                LinearGradient(
                    colors: [.clear, .white.opacity(0.9), JafarPalette.accentBlue, .clear],
                    startPoint: .leading,
                    endPoint: .trailing
                )
                .frame(width: 20, height: 30)
                .offset(x: sweeping ? 25 : -25)
                .mask(
                    Image(systemName: "brain.head.profile")
                        .font(.system(size: 25, weight: .medium))
                )
            }

            Group {
                Circle().frame(width: 2.5, height: 2.5).offset(x: -8, y: -8)
                Circle().frame(width: 2.5, height: 2.5).offset(x: 7, y: -5)
                Circle().frame(width: 2.5, height: 2.5).offset(x: 5, y: 8)
            }
            .foregroundStyle(JafarPalette.accentBlue.opacity(isAnalyzing ? 0.9 : 0.55))
        }
        .scaleEffect(isListening ? 0.96 : (breathing ? 1.04 : 0.98))
    }
}

struct CanonicalHomePrototypeView: View {
    @ObservedObject var dashboard: DashboardStore
    let demoMode: Bool
    let onMatter: (DashboardMatter) -> Void
    let onNavigate: (String) -> Void
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var haloBreath = false
    @State private var ringTurn = false
    @State private var sweepPhase = false
    @State private var selectedQuickAction: String?
    @State private var listeningPulse = false
    @State private var analyzing = false
    @State private var hoverItem: String?
    @StateObject private var voice: VoiceSessionViewModel

    init(
        dashboard: DashboardStore,
        demoMode: Bool,
        onMatter: @escaping (DashboardMatter) -> Void,
        onNavigate: @escaping (String) -> Void
    ) {
        self.dashboard = dashboard
        self.demoMode = demoMode
        self.onMatter = onMatter
        self.onNavigate = onNavigate
        _voice = StateObject(wrappedValue: VoiceSessionViewModel(
            commandClient: JafarClientFactory.commandClient(),
            userId: "local-user"
        ))
    }

    private var sourceMatters: [DashboardMatter] {
        (demoMode ? JusticeSamples.matters : dashboard.snapshot.matters)
            .sorted {
                if $0.overdueDeadlineCount != $1.overdueDeadlineCount {
                    return $0.overdueDeadlineCount > $1.overdueDeadlineCount
                }
                if $0.deadlineCount != $1.deadlineCount {
                    return $0.deadlineCount > $1.deadlineCount
                }
                return $0.title.localizedCaseInsensitiveCompare($1.title) == .orderedAscending
            }
    }

    private var matters: [CanonicalMatter] {
        sourceMatters.prefix(3).map { matter in
            CanonicalMatter(
                id: matter.id,
                source: matter,
                client: matter.clientName ?? matter.title,
                number: matter.caseNumber ?? "Номер дела не указан",
                priority: matterPriority(matter),
                progress: demoMode ? demoProgress(for: matter) : nil,
                action: matter.nextDeadlineTitle ?? "Ближайшее действие не указано",
                deadline: matter.nextDeadlineDate ?? "срок не указан",
                meta: matterMetadata(matter)
            )
        }
    }

    private var activities: [CanonicalActivity] {
        if demoMode {
            return [
                CanonicalActivity(id: "demo-activity-1", title: "Проанализирован документ", matter: "Павлик В.А.", timestamp: "10 мин"),
                CanonicalActivity(id: "demo-activity-2", title: "Найден процессуальный риск", matter: "Екименко А.С.", timestamp: "1 ч"),
                CanonicalActivity(id: "demo-activity-3", title: "Подготовлен черновик", matter: "ООО «Альфа»", timestamp: "вчера"),
                CanonicalActivity(id: "demo-activity-4", title: "Обновлена позиция", matter: "Общий обзор", timestamp: "вчера")
            ]
        }
        return dashboard.snapshot.signals.prefix(4).map { signal in
            CanonicalActivity(
                id: signal.id,
                title: signal.title,
                matter: sourceMatters.first(where: { $0.id == signal.matterId })?.clientName ?? "Общая сводка",
                timestamp: signal.dueDate ?? "Без срока"
            )
        }
    }

    private var taskRows: [CanonicalRailRow] {
        sourceMatters.compactMap { matter in
            guard let title = matter.nextDeadlineTitle, let date = matter.nextDeadlineDate else { return nil }
            return CanonicalRailRow(
                id: matter.id,
                date: date,
                title: title,
                matter: matter.caseNumber ?? "Номер дела не указан",
                urgency: matter.overdueDeadlineCount > 0 ? "требует внимания" : "срок"
            )
        }
        .prefix(4)
        .map { $0 }
    }

    private var hearingRows: [CanonicalRailRow] {
        sourceMatters.compactMap { matter in
            guard let title = matter.nextDeadlineTitle,
                  title.localizedCaseInsensitiveContains("заседан"),
                  let date = matter.nextDeadlineDate else { return nil }
            return CanonicalRailRow(
                id: matter.id,
                date: date,
                title: title,
                matter: matter.caseNumber ?? "Номер дела не указан",
                urgency: "ближайшее"
            )
        }
        .prefix(2)
        .map { $0 }
    }

    private var attentionCount: Int {
        max(
            dashboard.snapshot.pendingApprovals,
            dashboard.snapshot.signals.filter { $0.priority >= 50 || $0.requiresApproval }.count + dashboard.snapshot.overdueDeadlines
        )
    }

    private var nextDeadlineValue: String {
        sourceMatters.compactMap(\.nextDeadlineDate).sorted().first ?? "—"
    }

    private var isListening: Bool { voice.isListening }
    private var isAnalyzing: Bool { analyzing || dashboard.isLoading || voice.isSpeaking }
    private var isControl: Bool { dashboard.errorMessage != nil || dashboard.snapshot.pendingApprovals > 0 }

    private var systemStatusTitle: String {
        if dashboard.errorMessage != nil { return "Требуется решение" }
        return JafarAPIConfiguration.baseURL == nil ? "Локальный режим" : "Система активна"
    }

    private var systemStatusDetail: String {
        if let error = dashboard.errorMessage { return error }
        return JafarAPIConfiguration.baseURL == nil
            ? "JAFAR AI · данные не подключены"
            : "JAFAR AI · данные синхронизированы"
    }

    private var systemStatusColor: Color {
        dashboard.errorMessage != nil ? JafarPalette.warning : (JafarAPIConfiguration.baseURL == nil ? JafarPalette.warning : JafarPalette.success)
    }

    private var intelligenceStatus: String {
        if isListening { return "Слушаю команду" }
        if isControl { return "Требуется решение" }
        if isAnalyzing { return "Анализирует ваши дела" }
        return "Готов к диалогу"
    }

    private func matterPriority(_ matter: DashboardMatter) -> String {
        if matter.overdueDeadlineCount > 0 { return "Высокий приоритет" }
        if matter.deadlineCount > 0 { return "Средний приоритет" }
        return "Низкий приоритет"
    }

    private func matterMetadata(_ matter: DashboardMatter) -> String {
        let deadlines = "\(matter.deadlineCount) \(matter.deadlineCount == 1 ? "срок" : "срока")"
        return matter.overdueDeadlineCount > 0 ? "\(deadlines) · \(matter.overdueDeadlineCount) риск" : deadlines
    }

    private func demoProgress(for matter: DashboardMatter) -> Double {
        if matter.overdueDeadlineCount > 0 { return 0.75 }
        if matter.deadlineCount >= 4 { return 0.50 }
        return 0.25
    }

    var body: some View {
        GeometryReader { proxy in
            HStack(spacing: 0) {
                prototypeSidebar
                    .frame(width: 200)
                VStack(spacing: 0) {
                    prototypeHeader
                        .frame(height: 70)
                    HStack(alignment: .top, spacing: 12) {
                        VStack(spacing: 10) {
                            topMainGrid
                            commandBar
                            mattersActivity
                            lowerModules
                        }
                        .frame(maxWidth: .infinity)
                        prototypeRail
                            .frame(width: 270)
                    }
                    .padding(.horizontal, 14)
                    .padding(.bottom, 6)
                    prototypeFooter
                        .frame(height: 30)
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            }
            .frame(width: max(proxy.size.width, 1200), height: max(proxy.size.height, 760), alignment: .topLeading)
            .background(prototypeBackground)
        }
        .frame(minWidth: 1200, idealWidth: 1536, minHeight: 760, idealHeight: 1024)
        .preferredColorScheme(.dark)
    }

    private var prototypeBackground: some View {
        ZStack {
            LinearGradient(colors: [Color(red: 3 / 255, green: 7 / 255, blue: 14 / 255), JafarPalette.background], startPoint: .top, endPoint: .bottom)
            RadialGradient(colors: [JafarPalette.accentBlue.opacity(0.13), .clear], center: .center, startRadius: 40, endRadius: 650)
            RadialGradient(colors: [JafarPalette.goldGlow.opacity(0.10), .clear], center: .center, startRadius: 20, endRadius: 430)
            RadialGradient(colors: [.clear, .black.opacity(0.48)], center: .center, startRadius: 350, endRadius: 1000)
        }.ignoresSafeArea()
    }

    private var prototypeSidebar: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 8) { Image(systemName: "shield.lefthalf.filled").foregroundStyle(JafarPalette.accentGold); VStack(alignment: .leading, spacing: 1) { Text("JAFAR AI").font(JusticeTypography.title).foregroundStyle(JafarPalette.textPrimary); Text("ЮРИДИЧЕСКИЙ ПОМОЩНИК АДВОКАТА").font(.system(size: 9, weight: .medium, design: .rounded)).foregroundStyle(JafarPalette.textSecondary) } }
                .padding(.bottom, 7)
            ForEach([("Главная", "house.fill"), ("Дела", "briefcase.fill"), ("Календарь", "calendar"), ("Документы", "doc.text.fill"), ("Почта", "envelope.fill"), ("Правовой радар", "dot.radiowaves.left.and.right"), ("Практика", "books.vertical"), ("Черновики", "square.and.pencil"), ("Голосовые материалы", "waveform"), ("Аналитика", "chart.bar.xaxis"), ("Библиотека норм", "books.vertical.fill"), ("Проверка контрагентов", "person.crop.rectangle"), ("Настройки", "gearshape.fill")], id: \.0) { item in
                Button { onNavigate(item.0) } label: {
                    HStack(spacing: 8) { Image(systemName: item.1).frame(width: 16); Text(item.0).font(.system(size: 12, design: .rounded)); Spacer() }
                }
                    .buttonStyle(.plain)
                    .padding(.horizontal, 8).padding(.vertical, 5)
                    .foregroundStyle(item.0 == "Главная" || hoverItem == item.0 ? JafarPalette.accentGold : JafarPalette.textSecondary)
                    .background(item.0 == "Главная" ? JafarPalette.accent.opacity(0.18) : hoverItem == item.0 ? JafarPalette.accent.opacity(0.08) : .clear, in: RoundedRectangle(cornerRadius: 6))
                    .overlay(alignment: .leading) { Capsule().fill(item.0 == "Главная" ? JafarPalette.accentGold : .clear).frame(width: 2, height: 18) }
                    .onHover { inside in withAnimation(JafarMotion.fast) { hoverItem = inside ? item.0 : nil } }
            }
            Spacer(minLength: 4)
            CanonicalPanel { HStack(spacing: 8) { Circle().fill(JafarPalette.accentGold).frame(width: 26, height: 26).overlay(Text("ИИ").font(.caption).foregroundStyle(JafarPalette.background)); VStack(alignment: .leading, spacing: 2) { Text("Адвокат Иванов И.И.").font(.caption); Text("Профиль").font(.caption).foregroundStyle(JafarPalette.textMuted) } } }
            HStack(spacing: 6) { Circle().fill(systemStatusColor).frame(width: 6, height: 6); VStack(alignment: .leading, spacing: 1) { Text(systemStatusTitle).font(.caption); Text(systemStatusDetail).font(.system(size: 9)).foregroundStyle(JafarPalette.textMuted) } }.padding(.horizontal, 6)
        }
        .padding(12)
        .background(Color.black.opacity(0.18))
    }

    private var prototypeHeader: some View {
        HStack(alignment: .center) {
            VStack(alignment: .leading, spacing: 2) { Text("Доброе утро, Иван Иванович").font(.system(size: 24, weight: .semibold, design: .serif)); Text(systemStatusDetail).font(.system(size: 13)).foregroundStyle(JafarPalette.textSecondary) }
            Spacer()
            HStack(spacing: 8) { HStack { Image(systemName: "magnifyingglass"); Text("Поиск по делам и документам"); Text("⌘K").font(JusticeTypography.mono) }.font(.caption2).foregroundStyle(JafarPalette.textMuted).padding(8).frame(width: 230).background(JafarPalette.surface, in: RoundedRectangle(cornerRadius: 6)); Button { } label: { Image(systemName: "bell").overlay(alignment: .topTrailing) { Circle().fill(JafarPalette.danger).frame(width: 5, height: 5).offset(x: 3, y: -3) } }.buttonStyle(.plain).foregroundStyle(JafarPalette.accentGold); Button { } label: { Image(systemName: "gearshape") }.buttonStyle(.plain).foregroundStyle(JafarPalette.textSecondary); Button("+ Создать") { }.buttonStyle(.borderedProminent).tint(JafarPalette.accentGold) }
        }.padding(.horizontal, 16).overlay(alignment: .bottom) { Rectangle().fill(JafarPalette.divider).frame(height: 1) }
    }

    private var topMainGrid: some View {
        HStack(alignment: .top, spacing: 10) {
            CanonicalPanel(glow: JafarPalette.goldGlow) { VStack(alignment: .leading, spacing: 8) { Text("ФОКУС ДНЯ").font(JusticeTypography.title).foregroundStyle(JafarPalette.accentGold); focusRow("Требуют внимания", "\(attentionCount)", "exclamationmark.triangle.fill", JafarPalette.warning); focusRow("Новые письма", demoMode ? "1" : "—", "envelope.fill", JafarPalette.accentBlue); focusRow("Новые документы", demoMode ? "2" : "—", "doc.text.fill", JafarPalette.accentGold); focusRow("Ближайший срок", nextDeadlineValue, "calendar", JafarPalette.success) } }.frame(width: 190, height: 238)
            CanonicalPanel(glow: isAnalyzing ? JafarPalette.accentBlue : JafarPalette.goldGlow) {
                ZStack {
                    Circle().fill(JafarPalette.goldGlow.opacity(isAnalyzing ? 0.24 : 0.16)).blur(radius: 22).scaleEffect(haloBreath ? 1.07 : 0.92)
                    Circle().stroke(JafarPalette.accent.opacity(0.45), lineWidth: 1).frame(width: 190, height: 190).rotationEffect(.degrees(ringTurn ? 360 : 0))
                    if isAnalyzing {
                        Circle().trim(from: 0.10, to: 0.61).stroke(JafarPalette.accentBlue.opacity(0.82), style: StrokeStyle(lineWidth: 1, lineCap: .round)).frame(width: 174, height: 174).rotationEffect(.degrees(ringTurn ? -360 : 0))
                    }
                    Image("JusticeHero")
                        .resizable()
                        .scaledToFit()
                        .frame(maxWidth: .infinity, maxHeight: 220)
                        // The mask fades only the image perimeter. Its centre remains fully opaque.
                        .mask {
                            LinearGradient(stops: [.init(color: .clear, location: 0), .init(color: .white, location: 0.10), .init(color: .white, location: 0.90), .init(color: .clear, location: 1)], startPoint: .leading, endPoint: .trailing)
                                .mask(LinearGradient(stops: [.init(color: .clear, location: 0), .init(color: .white, location: 0.08), .init(color: .white, location: 0.92), .init(color: .clear, location: 1)], startPoint: .top, endPoint: .bottom))
                        }
                    if isAnalyzing {
                        LinearGradient(colors: [.clear, JafarPalette.goldHighlight.opacity(0.18), JafarPalette.accentBlue.opacity(0.12), .clear], startPoint: .topLeading, endPoint: .bottomTrailing)
                            .frame(width: 90)
                            .offset(x: sweepPhase ? 190 : -190)
                            .blur(radius: 8)
                            .allowsHitTesting(false)
                    }
                    VStack(alignment: .leading) { Spacer(); Text("ЮСТИЦИЯ").font(JusticeTypography.titleLarge); Text(systemStatusTitle).font(.caption).foregroundStyle(JafarPalette.accentGold) }.frame(maxWidth: .infinity, alignment: .leading)
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            }
            .frame(maxWidth: .infinity, minHeight: 238)
            CanonicalPanel(glow: isAnalyzing ? JafarPalette.accentBlue : (isControl ? JafarPalette.goldGlow : nil)) {
                VStack(alignment: .leading, spacing: 7) {
                    CanonicalIntelligenceEmblem(isAnalyzing: isAnalyzing, isListening: isListening, hasControlFocus: isControl || selectedQuickAction != nil, breathing: haloBreath, orbiting: ringTurn, sweeping: sweepPhase, reduceMotion: reduceMotion)
                    Text("JAFAR AI").font(JusticeTypography.title).foregroundStyle(JafarPalette.accentGold)
                    Text(intelligenceStatus).font(JusticeTypography.headline)
                    ForEach(["Правовой анализ", "Процессуальные риски", "Стратегию защиты", "Черновики документов"], id: \.self) { Text($0).font(.caption).foregroundStyle(JafarPalette.textSecondary) }
                    Button("Начать диалог") { beginAnalysis() }.buttonStyle(.borderedProminent).tint(JafarPalette.accentGold)
                }
            }
            .frame(width: 210, height: 238)
        }
        .onAppear { guard !reduceMotion else { return }; withAnimation(JafarMotion.ambient) { haloBreath = true }; withAnimation(.linear(duration: 18).repeatForever(autoreverses: false)) { ringTurn = true }; withAnimation(.easeInOut(duration: 2.8).repeatForever(autoreverses: true)) { sweepPhase = true } }
    }

    private func focusRow(_ title: String, _ value: String, _ icon: String, _ color: Color) -> some View { HStack(spacing: 7) { Image(systemName: icon).font(.caption).foregroundStyle(color); VStack(alignment: .leading, spacing: 1) { Text(title).font(.caption).foregroundStyle(JafarPalette.textSecondary); Text(value).font(JusticeTypography.headline).foregroundStyle(JafarPalette.textPrimary) } } }

    private var commandBar: some View {
        VStack(spacing: 6) {
            HStack {
                Image(systemName: "scalemass.fill").foregroundStyle(JafarPalette.accentGold)
                Text("Спросите Джафара...").font(JusticeTypography.headline).foregroundStyle(JafarPalette.textMuted)
                Spacer()
                Button { toggleListening() } label: {
                    ZStack {
                        Circle().fill(isListening ? JafarPalette.accentGold.opacity(0.30) : JafarPalette.accent.opacity(0.13))
                        Image(systemName: "mic.fill").foregroundStyle(JafarPalette.accentGold)
                        if isListening && !reduceMotion {
                            Circle().stroke(JafarPalette.accentGold, lineWidth: 1)
                                .scaleEffect(listeningPulse ? 1.58 : 1)
                                .opacity(listeningPulse ? 0.08 : 0.42)
                        }
                    }
                    .frame(width: 27, height: 27)
                }
                .buttonStyle(.plain)
            }
            .padding(9)
            .background(JafarPalette.surface, in: Capsule())
            .overlay {
                Capsule().stroke(isListening ? JafarPalette.accentGold : (isAnalyzing ? JafarPalette.accentBlue : JafarPalette.accent.opacity(0.34)), lineWidth: isListening ? 1.5 : 1)
                if isAnalyzing && !reduceMotion {
                    LinearGradient(colors: [.clear, JafarPalette.accentBlue.opacity(0.9), JafarPalette.goldHighlight.opacity(0.8), .clear], startPoint: .leading, endPoint: .trailing)
                        .frame(width: 80, height: 1.5)
                        .offset(x: sweepPhase ? 260 : -260)
                        .clipShape(Capsule())
                        .allowsHitTesting(false)
                }
            }

            HStack(spacing: 5) {
                ForEach(["Что требует моего внимания?", "Разбери последнее письмо", "Что нового по делу?", "Подготовь правовую позицию"], id: \.self) { action in
                    Button {
                        withAnimation(reduceMotion ? nil : JafarMotion.fast) { selectedQuickAction = action }
                        beginAnalysis()
                    } label: {
                        Text(action).font(.caption)
                            .foregroundStyle(selectedQuickAction == action ? JafarPalette.textPrimary : JafarPalette.accentGold)
                            .padding(.horizontal, 8).padding(.vertical, 4)
                            .background(selectedQuickAction == action ? JafarPalette.accent.opacity(0.27) : .clear, in: Capsule())
                            .overlay(Capsule().stroke(JafarPalette.accent.opacity(selectedQuickAction == action ? 0.8 : 0.4)))
                    }
                    .buttonStyle(.plain)
                }
            }
        }
    }

    private func beginAnalysis() {
        withAnimation(reduceMotion ? nil : JafarMotion.normal) { analyzing = true }
        Task { @MainActor in
            try? await Task.sleep(for: .seconds(4))
            guard !isListening else { return }
            withAnimation(reduceMotion ? nil : JafarMotion.normal) { analyzing = false }
        }
    }

    private func toggleListening() {
        Task {
            if voice.isListening {
                await voice.stopAndSend()
                listeningPulse = false
            } else {
                analyzing = false
                await voice.start()
                guard voice.isListening, !reduceMotion else { return }
                withAnimation(.easeInOut(duration: 1.4).repeatForever(autoreverses: true)) {
                    listeningPulse = true
                }
            }
        }
    }

    private var mattersActivity: some View {
        HStack(alignment: .top, spacing: 10) {
            VStack(alignment: .leading, spacing: 6) {
                Text("МОИ ДЕЛА").font(JusticeTypography.title).foregroundStyle(JafarPalette.textPrimary)
                HStack(spacing: 7) {
                    ForEach(matters) { matter in
                        CanonicalMatterCard(matter: matter, action: {
                            if let source = matter.source { onMatter(source) }
                        })
                    }
                    ForEach(0..<max(0, 3 - matters.count), id: \.self) { _ in
                        CanonicalEmptyMatterCard()
                    }
                    NewCanonicalMatterCard()
                }
            }
            .frame(maxWidth: .infinity)

            CanonicalPanel {
                VStack(alignment: .leading, spacing: 7) {
                    Text("АКТИВНОСТЬ").font(JusticeTypography.title).foregroundStyle(JafarPalette.accentGold)
                    if activities.isEmpty {
                        structuredEmptyState("Событий в сводке нет", icon: "clock")
                    } else {
                        ForEach(activities) { row in
                            HStack(alignment: .top, spacing: 6) {
                                Image(systemName: "checkmark.circle").font(.caption2).foregroundStyle(JafarPalette.accentGold)
                                VStack(alignment: .leading, spacing: 1) {
                                    Text(row.title).font(.caption2).lineLimit(1)
                                    Text(row.matter).font(.caption2).foregroundStyle(JafarPalette.textSecondary).lineLimit(1)
                                    Text(row.timestamp).font(.caption2).foregroundStyle(JafarPalette.textMuted).lineLimit(1)
                                }
                            }
                        }
                    }
                }
            }
            .frame(width: 220, height: 150)
        }
    }

    private var lowerModules: some View {
        HStack(spacing: 10) {
            CanonicalPanel {
                VStack(alignment: .leading, spacing: 5) {
                    Label("ПРАВОВОЙ РАДАР", systemImage: "dot.radiowaves.left.and.right").font(.caption).foregroundStyle(JafarPalette.accentGold)
                    if demoMode {
                        Text("12 новых изменений").font(JusticeTypography.headline)
                        Text("Пленум ВС РФ · сегодня").font(.caption2).foregroundStyle(JafarPalette.textSecondary)
                        Text("Изменения ГПК · вчера").font(.caption2).foregroundStyle(JafarPalette.textSecondary)
                        Text("Практика арбитража · 2 дн.").font(.caption2).foregroundStyle(JafarPalette.textSecondary)
                    } else {
                        structuredEmptyState("Источник радара не подключён", icon: "dot.radiowaves.left.and.right")
                    }
                    Button("Открыть радар") { onNavigate("Правовой радар") }.buttonStyle(.plain).font(.caption2).foregroundStyle(JafarPalette.accentGold)
                }
            }
            .frame(maxWidth: .infinity, minHeight: 135)

            CanonicalPanel {
                VStack(alignment: .leading, spacing: 5) {
                    Label("AI-АНАЛИТИКА", systemImage: "chart.pie.fill").font(.caption).foregroundStyle(JafarPalette.accentGold)
                    if demoMode {
                        HStack { riskGauge(value: "57%"); VStack(alignment: .leading, spacing: 2) { Text("Средний риск").font(.caption); Text("Высокий 18%").font(.caption2).foregroundStyle(JafarPalette.warning); Text("Средний 39% · Низкий 43%").font(.caption2).foregroundStyle(JafarPalette.textMuted) } }
                        Text("↗ 8% улучшение за неделю").font(.caption2).foregroundStyle(JafarPalette.success)
                    } else {
                        structuredEmptyState("Безопасные агрегаты недоступны", icon: "chart.pie")
                    }
                }
            }
            .frame(maxWidth: .infinity, minHeight: 135)

            CanonicalPanel {
                VStack(alignment: .leading, spacing: 5) {
                    Label("ГОЛОСОВЫЕ МАТЕРИАЛЫ", systemImage: "waveform").font(.caption).foregroundStyle(JafarPalette.accentGold)
                    if demoMode {
                        waveform
                        Text("3 записи · 42 мин").font(.caption2).foregroundStyle(JafarPalette.textSecondary)
                        Text("Последняя запись · сегодня, 09:42").font(.caption2).foregroundStyle(JafarPalette.textMuted)
                    } else {
                        structuredEmptyState("Метаданные записей недоступны", icon: "waveform")
                    }
                    Button("Открыть материалы") { onNavigate("Голосовые материалы") }.buttonStyle(.plain).font(.caption2).foregroundStyle(JafarPalette.accentGold)
                }
            }
            .frame(maxWidth: .infinity, minHeight: 135)
        }
    }

    private var prototypeRail: some View {
        VStack(spacing: 10) {
            CanonicalPanel {
                VStack(alignment: .leading, spacing: 7) {
                    Label("ЗАДАЧИ И СРОКИ", systemImage: "calendar.badge.clock").font(.caption).foregroundStyle(JafarPalette.accentGold)
                    if taskRows.isEmpty {
                        structuredEmptyState("Сроков в сводке нет", icon: "calendar")
                    } else {
                        ForEach(taskRows) { row in railRow(row, color: JafarPalette.warning) }
                    }
                }
            }
            .frame(minHeight: 198)

            CanonicalPanel {
                VStack(alignment: .leading, spacing: 7) {
                    Label("БЛИЖАЙШИЕ ЗАСЕДАНИЯ", systemImage: "building.columns").font(.caption).foregroundStyle(JafarPalette.accentGold)
                    if hearingRows.isEmpty {
                        structuredEmptyState("Заседаний в сводке нет", icon: "building.columns")
                    } else {
                        ForEach(hearingRows) { row in railRow(row, color: JafarPalette.accentGold) }
                    }
                }
            }
            .frame(minHeight: 112)

            CanonicalPanel { Text("«Право — это искусство добра и справедливости»").font(JusticeTypography.callout).italic().foregroundStyle(JafarPalette.textPrimary); Text("— Цицерон").font(.caption2).foregroundStyle(JafarPalette.textMuted) }
        }
    }

    private var waveform: some View {
        HStack(alignment: .bottom, spacing: 3) { ForEach(0..<20, id: \.self) { index in Capsule().fill(index % 4 == 0 ? JafarPalette.goldHighlight : JafarPalette.accentBlue).frame(width: 3, height: CGFloat(8 + (index % 6) * 4) * (haloBreath ? 1.08 : 0.92)) } }
    }

    private func riskGauge(value: String) -> some View {
        ZStack { Circle().stroke(JafarPalette.divider, lineWidth: 7); Circle().trim(from: 0, to: 0.57).stroke(JafarPalette.accentGold, style: StrokeStyle(lineWidth: 7, lineCap: .round)).rotationEffect(.degrees(-90)); Text(value).font(JusticeTypography.headline) }.frame(width: 52, height: 52)
    }

    private func structuredEmptyState(_ title: String, icon: String) -> some View {
        HStack(spacing: 6) { Image(systemName: icon).font(.caption).foregroundStyle(JafarPalette.textMuted); Text(title).font(.caption2).foregroundStyle(JafarPalette.textSecondary).lineLimit(2) }
            .frame(maxWidth: .infinity, alignment: .leading)
    }

    private func railRow(_ row: CanonicalRailRow, color: Color) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            HStack { Text(row.date).font(.caption2.monospacedDigit()).foregroundStyle(JafarPalette.accentGold).lineLimit(1); Spacer(); Text(row.urgency).font(.caption2).foregroundStyle(color).lineLimit(1) }
            Text(row.title).font(.caption).lineLimit(1)
            Text(row.matter).font(.caption2).foregroundStyle(JafarPalette.textMuted).lineLimit(1)
            Divider().overlay(JafarPalette.divider)
        }
    }

    private var prototypeFooter: some View { HStack(spacing: 16) { Label("Шифрование: активно", systemImage: "lock.fill"); Label("Резервное копирование: сегодня, 03:00", systemImage: "externaldrive.fill"); Label("Синхронизация: активно", systemImage: "arrow.triangle.2.circlepath"); Spacer(); Text("JAFAR AI защищает ваши данные и помогает управлять делами") }.font(.caption2).foregroundStyle(JafarPalette.textMuted).padding(.horizontal, 14).overlay(alignment: .top) { Rectangle().fill(JafarPalette.divider).frame(height: 1) } }
}

private struct CanonicalMatterCard: View {
    let matter: CanonicalMatter
    let action: () -> Void
    @State private var fill = false
    var body: some View { Button(action: action) { CanonicalPanel(glow: (matter.progress ?? 0) > 0.7 ? JafarPalette.warning : .clear) { VStack(alignment: .leading, spacing: 5) { HStack { Text(matter.client).font(JusticeTypography.title).lineLimit(1).minimumScaleFactor(0.70).allowsTightening(true); Spacer(minLength: 2); Text(matter.priority.replacingOccurrences(of: " приоритет", with: "")).font(.system(size: 9, weight: .semibold)).foregroundStyle((matter.progress ?? 0) > 0.7 ? JafarPalette.warning : JafarPalette.accentGold) }; Text(matter.number).font(JusticeTypography.mono).foregroundStyle(JafarPalette.textSecondary).lineLimit(1); HStack { Text(matter.progress.map { "\(Int($0 * 100))%" } ?? "—").font(.caption).foregroundStyle(JafarPalette.accentGold); ProgressView(value: fill ? (matter.progress ?? 0) : 0).tint(JafarPalette.accentGold) }; Text("Следующее действие").font(.caption).foregroundStyle(JafarPalette.textMuted); Text(matter.action).font(.caption).lineLimit(1); HStack { Text("До \(matter.deadline)"); Spacer(); Text(matter.meta) }.font(.caption).foregroundStyle(JafarPalette.textMuted).lineLimit(1) }.frame(width: 148, alignment: .leading) } }.buttonStyle(.plain).onAppear { withAnimation(JafarMotion.slow) { fill = true } }.frame(height: 150) }
}

private struct CanonicalEmptyMatterCard: View {
    var body: some View { CanonicalPanel { VStack(alignment: .leading, spacing: 6) { Image(systemName: "briefcase").font(.title3).foregroundStyle(JafarPalette.textMuted); Text("Нет дела").font(JusticeTypography.headline); Text("Подключённые дела появятся здесь").font(.caption2).foregroundStyle(JafarPalette.textMuted).lineLimit(2); Spacer() }.frame(width: 148, alignment: .leading) }.frame(height: 150) }
}

private struct NewCanonicalMatterCard: View {
    var body: some View { CanonicalPanel { VStack(spacing: 7) { Image(systemName: "plus.circle").font(.title2).foregroundStyle(JafarPalette.accentGold); Text("+ Новое дело").font(JusticeTypography.headline); Text("Создать или загрузить").font(.caption2).foregroundStyle(JafarPalette.textMuted); Spacer() }.frame(width: 120, alignment: .center) }.frame(height: 150) }
}

#Preview("Canonical JAFAR desktop home") {
    CanonicalHomePrototypeView(
        dashboard: DashboardStore(client: LocalDashboardClient()),
        demoMode: true,
        onMatter: { _ in },
        onNavigate: { _ in }
    )
}
