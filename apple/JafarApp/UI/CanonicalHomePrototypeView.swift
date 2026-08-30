import SwiftUI

private struct CanonicalMatter: Identifiable {
    let id = UUID()
    let client: String
    let number: String
    let priority: String
    let progress: Double
    let action: String
    let deadline: String
    let meta: String
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

struct CanonicalHomePrototypeView: View {
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var haloBreath = false
    @State private var ringTurn = false
    @State private var aiPulse = false
    @State private var sweepPhase = false
    @State private var selectedQuickAction: String?
    @State private var listening = false
    @State private var hoverItem: String?

    private let matters = [
        CanonicalMatter(client: "Павлик В.А.", number: "A-1234/2026", priority: "Высокий приоритет", progress: 0.75, action: "Подать возражения", deadline: "20.05.2026", meta: "3 документа"),
        CanonicalMatter(client: "Екименко А.С.", number: "E-5678/2026", priority: "Средний приоритет", progress: 0.50, action: "Сверить позицию", deadline: "22.05.2026", meta: "2 источника"),
        CanonicalMatter(client: "ООО «Ромашка»", number: "П-9101/2026", priority: "Низкий приоритет", progress: 0.25, action: "Проверить договор", deadline: "25.05.2026", meta: "1 риск")
    ]

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
            HStack(spacing: 8) { Image(systemName: "shield.lefthalf.filled").foregroundStyle(JafarPalette.accentGold); VStack(alignment: .leading, spacing: 1) { Text("JAFAR AI").font(JusticeTypography.title).foregroundStyle(JafarPalette.textPrimary); Text("ЮРИДИЧЕСКИЙ ПОМОЩНИК АДВОКАТА").font(.system(size: 8, weight: .medium, design: .rounded)).foregroundStyle(JafarPalette.textSecondary) } }
                .padding(.bottom, 7)
            ForEach([("Главная", "house.fill"), ("Дела", "briefcase.fill"), ("Календарь", "calendar"), ("Документы", "doc.text.fill"), ("Почта", "envelope.fill"), ("Правовой радар", "dot.radiowaves.left.and.right"), ("Практика", "books.vertical"), ("Черновики", "square.and.pencil"), ("Голосовые материалы", "waveform"), ("Аналитика", "chart.bar.xaxis"), ("Библиотека норм", "books.vertical.fill"), ("Проверка контрагентов", "person.crop.rectangle"), ("Настройки", "gearshape.fill")], id: \.0) { item in
                HStack(spacing: 8) { Image(systemName: item.1).frame(width: 16); Text(item.0).font(.system(size: 11, design: .rounded)); Spacer() }
                    .padding(.horizontal, 8).padding(.vertical, 5)
                    .foregroundStyle(item.0 == "Главная" || hoverItem == item.0 ? JafarPalette.accentGold : JafarPalette.textSecondary)
                    .background(item.0 == "Главная" ? JafarPalette.accent.opacity(0.18) : hoverItem == item.0 ? JafarPalette.accent.opacity(0.08) : .clear, in: RoundedRectangle(cornerRadius: 6))
                    .overlay(alignment: .leading) { Capsule().fill(item.0 == "Главная" ? JafarPalette.accentGold : .clear).frame(width: 2, height: 18) }
                    .onHover { inside in withAnimation(JafarMotion.fast) { hoverItem = inside ? item.0 : nil } }
            }
            Spacer(minLength: 4)
            CanonicalPanel { HStack(spacing: 8) { Circle().fill(JafarPalette.accentGold).frame(width: 26, height: 26).overlay(Text("ИИ").font(.caption2).foregroundStyle(JafarPalette.background)); VStack(alignment: .leading, spacing: 2) { Text("Адвокат Иванов И.И.").font(.caption2); Text("Профиль").font(.caption2).foregroundStyle(JafarPalette.textMuted) } } }
            HStack(spacing: 6) { Circle().fill(JafarPalette.success).frame(width: 6, height: 6); VStack(alignment: .leading, spacing: 1) { Text("Система активна").font(.caption2); Text("JAFAR AI v1.0.0 · Все сервисы работают").font(.system(size: 8)).foregroundStyle(JafarPalette.textMuted) } }.padding(.horizontal, 6)
        }
        .padding(12)
        .background(Color.black.opacity(0.18))
    }

    private var prototypeHeader: some View {
        HStack(alignment: .center) {
            VStack(alignment: .leading, spacing: 2) { Text("Доброе утро, Иван Иванович").font(JusticeTypography.titleLarge); Text("JAFAR AI готов служить вашей практике").font(.caption).foregroundStyle(JafarPalette.textSecondary) }
            Spacer()
            HStack(spacing: 8) { HStack { Image(systemName: "magnifyingglass"); Text("Поиск по делам и документам"); Text("⌘K").font(JusticeTypography.mono) }.font(.caption2).foregroundStyle(JafarPalette.textMuted).padding(8).frame(width: 230).background(JafarPalette.surface, in: RoundedRectangle(cornerRadius: 6)); Button { } label: { Image(systemName: "bell").overlay(alignment: .topTrailing) { Circle().fill(JafarPalette.danger).frame(width: 5, height: 5).offset(x: 3, y: -3) } }.buttonStyle(.plain).foregroundStyle(JafarPalette.accentGold); Button { } label: { Image(systemName: "gearshape") }.buttonStyle(.plain).foregroundStyle(JafarPalette.textSecondary); Button("+ Создать") { }.buttonStyle(.borderedProminent).tint(JafarPalette.accentGold) }
        }.padding(.horizontal, 16).overlay(alignment: .bottom) { Rectangle().fill(JafarPalette.divider).frame(height: 1) }
    }

    private var topMainGrid: some View {
        HStack(alignment: .top, spacing: 10) {
            CanonicalPanel(glow: JafarPalette.goldGlow) { VStack(alignment: .leading, spacing: 8) { Text("ФОКУС ДНЯ").font(JusticeTypography.title).foregroundStyle(JafarPalette.accentGold); focusRow("Требуют внимания", "3", "exclamationmark.triangle.fill", JafarPalette.warning); focusRow("Новые письма", "1", "envelope.fill", JafarPalette.accentBlue); focusRow("Новые документы", "2", "doc.text.fill", JafarPalette.accentGold); focusRow("Заседание завтра", "10:30", "calendar", JafarPalette.success) } }.frame(width: 190, height: 238)
            CanonicalPanel(glow: JafarPalette.goldGlow) { ZStack { Circle().fill(JafarPalette.goldGlow.opacity(0.16)).blur(radius: 22).scaleEffect(haloBreath ? 1.07 : 0.92); Circle().stroke(JafarPalette.accent.opacity(0.45), lineWidth: 1).frame(width: 190, height: 190).rotationEffect(.degrees(ringTurn ? 360 : 0)); Image("JusticeHero").resizable().scaledToFit().frame(maxWidth: .infinity, maxHeight: 220).mask(RadialGradient(colors: [.clear, .white, .white, .clear], center: .center, startRadius: 55, endRadius: 170)); LinearGradient(colors: [.clear, JafarPalette.goldHighlight.opacity(0.12), JafarPalette.accentBlue.opacity(0.08), .clear], startPoint: .topLeading, endPoint: .bottomTrailing).frame(width: 90).offset(x: sweepPhase ? 190 : -190).blur(radius: 8); VStack(alignment: .leading) { Spacer(); Text("ЮСТИЦИЯ").font(JusticeTypography.titleLarge); Text("Система активна").font(.caption2).foregroundStyle(JafarPalette.accentGold) }.frame(maxWidth: .infinity, alignment: .leading) }.frame(maxWidth: .infinity, maxHeight: .infinity) }.frame(maxWidth: .infinity, minHeight: 238)
            CanonicalPanel(glow: aiPulse ? JafarPalette.accentBlue : nil) { VStack(alignment: .leading, spacing: 7) { ZStack { Circle().stroke(JafarPalette.accentBlue.opacity(0.4), lineWidth: 1); Circle().trim(from: 0.08, to: 0.76).stroke(JafarPalette.accentGold, style: StrokeStyle(lineWidth: 2, lineCap: .round)).rotationEffect(.degrees(aiPulse ? 360 : 0)); Image(systemName: "scalemass.fill").foregroundStyle(JafarPalette.accentGold) }.frame(width: 48, height: 48); Text("JAFAR AI").font(JusticeTypography.title).foregroundStyle(JafarPalette.accentGold); Text("Анализирует ваши дела").font(JusticeTypography.headline); ForEach(["Правовой анализ", "Процессуальные риски", "Стратегию защиты", "Черновики документов"], id: \.self) { Text($0).font(.caption2).foregroundStyle(JafarPalette.textSecondary) }; Button("Начать диалог") { }.buttonStyle(.borderedProminent).tint(JafarPalette.accentGold) } }.frame(width: 210, height: 238)
        }
        .onAppear { guard !reduceMotion else { return }; withAnimation(JafarMotion.ambient) { haloBreath = true }; withAnimation(.linear(duration: 18).repeatForever(autoreverses: false)) { ringTurn = true }; withAnimation(.linear(duration: 6).repeatForever(autoreverses: false)) { aiPulse = true }; withAnimation(.easeInOut(duration: 4).repeatForever(autoreverses: true)) { sweepPhase = true } }
    }

    private func focusRow(_ title: String, _ value: String, _ icon: String, _ color: Color) -> some View { HStack(spacing: 7) { Image(systemName: icon).font(.caption).foregroundStyle(color); VStack(alignment: .leading, spacing: 1) { Text(title).font(.caption2).foregroundStyle(JafarPalette.textSecondary); Text(value).font(JusticeTypography.headline).foregroundStyle(JafarPalette.textPrimary) } } }

    private var commandBar: some View { VStack(spacing: 6) { HStack { Image(systemName: "scalemass.fill").foregroundStyle(JafarPalette.accentGold); Text("Спросите Джафара...").font(JusticeTypography.headline).foregroundStyle(JafarPalette.textMuted); Spacer(); Button { withAnimation(JafarMotion.normal) { listening.toggle() } } label: { ZStack { Circle().fill(listening ? JafarPalette.accentGold.opacity(0.3) : JafarPalette.accent.opacity(0.13)); Image(systemName: "mic.fill").foregroundStyle(JafarPalette.accentGold); if listening && !reduceMotion { Circle().stroke(JafarPalette.accentGold, lineWidth: 1).scaleEffect(1.4).opacity(0.2) } }.frame(width: 27, height: 27) }.buttonStyle(.plain) }.padding(9).background(JafarPalette.surface, in: Capsule()).overlay(Capsule().stroke(listening ? JafarPalette.accentGold : JafarPalette.accent.opacity(0.34), lineWidth: listening ? 1.5 : 1)); HStack(spacing: 5) { ForEach(["Что требует моего внимания?", "Разбери последнее письмо", "Что нового по делу?", "Подготовь правовую позицию"], id: \.self) { action in Button { withAnimation(JafarMotion.fast) { selectedQuickAction = action } } label: { Text(action).font(.caption2).foregroundStyle(selectedQuickAction == action ? JafarPalette.textPrimary : JafarPalette.accentGold).padding(.horizontal, 8).padding(.vertical, 4).background(selectedQuickAction == action ? JafarPalette.accent.opacity(0.27) : .clear, in: Capsule()).overlay(Capsule().stroke(JafarPalette.accent.opacity(selectedQuickAction == action ? 0.8 : 0.4))) }.buttonStyle(.plain) } } .overlay(alignment: .top) { if !reduceMotion { LinearGradient(colors: [.clear, JafarPalette.accentBlue.opacity(0.35), .clear], startPoint: .leading, endPoint: .trailing).frame(width: 60, height: 1).offset(x: sweepPhase ? 240 : -240).allowsHitTesting(false) } } } }

    private var mattersActivity: some View { HStack(alignment: .top, spacing: 10) { VStack(alignment: .leading, spacing: 6) { Text("МОИ ДЕЛА").font(JusticeTypography.title).foregroundStyle(JafarPalette.textPrimary); HStack(spacing: 7) { ForEach(matters) { matter in CanonicalMatterCard(matter: matter) }; NewCanonicalMatterCard() } }.frame(maxWidth: .infinity); CanonicalPanel { VStack(alignment: .leading, spacing: 7) { Text("АКТИВНОСТЬ").font(JusticeTypography.title).foregroundStyle(JafarPalette.accentGold); ForEach([("Проанализирован документ", "Павлик В.А.", "10 мин"), ("Найден процессуальный риск", "Екименко А.С.", "1 ч"), ("Подготовлен черновик", "ООО «Ромашка»", "вчера"), ("Обновлена позиция", "Общий обзор", "вчера")], id: \.0) { row in HStack(alignment: .top, spacing: 6) { Image(systemName: "checkmark.circle").font(.caption2).foregroundStyle(JafarPalette.accentGold); VStack(alignment: .leading, spacing: 1) { Text(row.0).font(.caption2); Text(row.1).font(.caption2).foregroundStyle(JafarPalette.textSecondary); Text(row.2).font(.caption2).foregroundStyle(JafarPalette.textMuted) } } } } }.frame(width: 220, height: 150) } }

    private var lowerModules: some View { HStack(spacing: 10) { CanonicalPanel { VStack(alignment: .leading, spacing: 5) { Label("ПРАВОВОЙ РАДАР", systemImage: "dot.radiowaves.left.and.right").font(.caption).foregroundStyle(JafarPalette.accentGold); Text("12 новых изменений").font(JusticeTypography.headline); Text("Пленум ВС РФ · сегодня").font(.caption2).foregroundStyle(JafarPalette.textSecondary); Text("Изменения ГПК · вчера").font(.caption2).foregroundStyle(JafarPalette.textSecondary); Text("Практика арбитража · 2 дн.").font(.caption2).foregroundStyle(JafarPalette.textSecondary); Button("Открыть радар") { }.buttonStyle(.plain).font(.caption2).foregroundStyle(JafarPalette.accentGold) } }.frame(maxWidth: .infinity, minHeight: 135); CanonicalPanel { VStack(alignment: .leading, spacing: 5) { Label("AI-АНАЛИТИКА", systemImage: "chart.pie.fill").font(.caption).foregroundStyle(JafarPalette.accentGold); HStack { ZStack { Circle().stroke(JafarPalette.divider, lineWidth: 7); Circle().trim(from: 0, to: 0.57).stroke(JafarPalette.accentGold, style: StrokeStyle(lineWidth: 7, lineCap: .round)).rotationEffect(.degrees(-90)); Text("57%").font(JusticeTypography.headline) }.frame(width: 52, height: 52); VStack(alignment: .leading, spacing: 2) { Text("Средний риск").font(.caption); Text("Высокий 18%").font(.caption2).foregroundStyle(JafarPalette.warning); Text("Средний 39% · Низкий 43%").font(.caption2).foregroundStyle(JafarPalette.textMuted) } }; Text("↗ 8% улучшение за неделю").font(.caption2).foregroundStyle(JafarPalette.success) } }.frame(maxWidth: .infinity, minHeight: 135); CanonicalPanel { VStack(alignment: .leading, spacing: 5) { Label("ГОЛОСОВЫЕ МАТЕРИАЛЫ", systemImage: "waveform").font(.caption).foregroundStyle(JafarPalette.accentGold); HStack(alignment: .bottom, spacing: 3) { ForEach(0..<20, id: \.self) { index in Capsule().fill(index % 4 == 0 ? JafarPalette.goldHighlight : JafarPalette.accentBlue).frame(width: 3, height: CGFloat(8 + (index % 6) * 4) * (haloBreath ? 1.08 : 0.92)) } }; Text("3 записи · 42 мин").font(.caption2).foregroundStyle(JafarPalette.textSecondary); Text("Последняя запись · сегодня, 09:42").font(.caption2).foregroundStyle(JafarPalette.textMuted); Button("Открыть материалы") { }.buttonStyle(.plain).font(.caption2).foregroundStyle(JafarPalette.accentGold) } }.frame(maxWidth: .infinity, minHeight: 135) } }

    private var prototypeRail: some View { VStack(spacing: 10) { CanonicalPanel { VStack(alignment: .leading, spacing: 7) { Label("ЗАДАЧИ И СРОКИ", systemImage: "calendar.badge.clock").font(.caption).foregroundStyle(JafarPalette.accentGold); ForEach([("20.05", "Подать возражения", "A-1234/2026", "3 дн."), ("сегодня", "Проверить источник", "E-5678/2026", "до 18:00"), ("22.05", "Подготовить вопросы", "П-9101/2026", "5 дн."), ("25.05", "Сверить приложения", "П-9101/2026", "7 дн.")], id: \.0) { row in VStack(alignment: .leading, spacing: 2) { HStack { Text(row.0).font(.caption2.monospacedDigit()).foregroundStyle(JafarPalette.accentGold); Spacer(); Text(row.3).font(.caption2).foregroundStyle(JafarPalette.warning) }; Text(row.1).font(.caption); Text(row.2).font(.caption2).foregroundStyle(JafarPalette.textMuted); Divider().overlay(JafarPalette.divider) } } } }; CanonicalPanel { VStack(alignment: .leading, spacing: 7) { Label("БЛИЖАЙШИЕ ЗАСЕДАНИЯ", systemImage: "building.columns").font(.caption).foregroundStyle(JafarPalette.accentGold); ForEach([("18.04 · 10:30", "Арбитражный суд", "A-1234/2026", "Завтра"), ("21.04 · 14:00", "Районный суд", "E-5678/2026", "4 дня")], id: \.0) { row in VStack(alignment: .leading, spacing: 2) { HStack { Text(row.0).font(.caption2.monospacedDigit()); Spacer(); Text(row.3).font(.caption2).foregroundStyle(JafarPalette.accentGold) }; Text(row.1).font(.caption2).foregroundStyle(JafarPalette.textSecondary); Text(row.2).font(.caption2).foregroundStyle(JafarPalette.textMuted) } } } }; CanonicalPanel { Text("«Право — это искусство добра и справедливости»").font(JusticeTypography.callout).italic().foregroundStyle(JafarPalette.textPrimary); Text("— Цицерон").font(.caption2).foregroundStyle(JafarPalette.textMuted) } } }

    private var prototypeFooter: some View { HStack(spacing: 16) { Label("Шифрование: активно", systemImage: "lock.fill"); Label("Резервное копирование: сегодня, 03:00", systemImage: "externaldrive.fill"); Label("Синхронизация: активно", systemImage: "arrow.triangle.2.circlepath"); Spacer(); Text("JAFAR AI защищает ваши данные и помогает управлять делами") }.font(.caption2).foregroundStyle(JafarPalette.textMuted).padding(.horizontal, 14).overlay(alignment: .top) { Rectangle().fill(JafarPalette.divider).frame(height: 1) } }
}

private struct CanonicalMatterCard: View {
    let matter: CanonicalMatter
    @State private var fill = false
    var body: some View { CanonicalPanel(glow: matter.progress > 0.7 ? JafarPalette.warning : .clear) { VStack(alignment: .leading, spacing: 5) { HStack { Text(matter.client).font(JusticeTypography.title).lineLimit(1); Spacer(); Text(matter.priority.replacingOccurrences(of: " приоритет", with: "")).font(.system(size: 8, weight: .semibold)).foregroundStyle(matter.progress > 0.7 ? JafarPalette.warning : JafarPalette.accentGold) }; Text(matter.number).font(JusticeTypography.mono).foregroundStyle(JafarPalette.textSecondary); HStack { Text("\(Int(matter.progress * 100))%").font(.caption2).foregroundStyle(JafarPalette.accentGold); ProgressView(value: fill ? matter.progress : 0).tint(JafarPalette.accentGold) }; Text("Следующее действие").font(.caption2).foregroundStyle(JafarPalette.textMuted); Text(matter.action).font(.caption2); HStack { Text("До \(matter.deadline)"); Spacer(); Text(matter.meta) }.font(.caption2).foregroundStyle(JafarPalette.textMuted) }.frame(width: 148, alignment: .leading) }.onAppear { withAnimation(JafarMotion.slow) { fill = true } }.frame(height: 150) }
}

private struct NewCanonicalMatterCard: View {
    var body: some View { CanonicalPanel { VStack(spacing: 7) { Image(systemName: "plus.circle").font(.title2).foregroundStyle(JafarPalette.accentGold); Text("+ Новое дело").font(JusticeTypography.headline); Text("Создать или загрузить").font(.caption2).foregroundStyle(JafarPalette.textMuted); Spacer() }.frame(width: 120, alignment: .center) }.frame(height: 150) }
}

#Preview("Canonical JAFAR desktop home") { CanonicalHomePrototypeView() }
