import SwiftUI

private enum CalendarEventTone: Equatable {
    case deadline, hearing, investigation, meeting, task, filed, completed

    var color: Color {
        switch self {
        case .deadline: JafarPalette.warning
        case .hearing, .filed: JafarPalette.accentGold
        case .investigation, .meeting: JafarPalette.accentBlue
        case .task: JafarPalette.textSecondary
        case .completed: JafarPalette.success
        }
    }

    var symbol: String {
        switch self {
        case .deadline: "exclamationmark.triangle.fill"
        case .hearing: "building.columns.fill"
        case .investigation: "magnifyingglass"
        case .meeting: "person.2.fill"
        case .task: "checklist"
        case .filed: "tray.and.arrow.up.fill"
        case .completed: "checkmark.circle.fill"
        }
    }

    var label: String {
        switch self {
        case .deadline: "Процессуальный срок"
        case .hearing: "Судебное заседание"
        case .investigation: "Следственное действие"
        case .meeting: "Встреча"
        case .task: "Задача"
        case .filed: "Подача документа"
        case .completed: "Выполнено"
        }
    }
}

private struct CalendarPrototypeEvent: Identifiable {
    let id: String
    let day: Int
    let time: String
    let title: String
    let caseNumber: String
    let tone: CalendarEventTone
}

private struct CriticalDeadline: Identifiable {
    let id: String
    let date: String
    let remaining: String
    let action: String
    let matter: String
    let urgent: Bool
}

struct CanonicalCalendarPrototypeView: View {
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var selectedDay = 20
    @State private var hoveredEventID: String?
    @State private var selectedEvent: CalendarPrototypeEvent?
    @State private var haloBreath = false
    @State private var ringTurn = false
    @State private var syncSweep = false
    @State private var syncing = false
    @State private var syncTurn = false
    @State private var calendarMode = "Месяц"
    @State private var urgentPulse = false

    private let events = [
        CalendarPrototypeEvent(id: "hearing-18", day: 18, time: "10:30", title: "Судебное заседание", caseNumber: "A-1234/2026", tone: .hearing),
        CalendarPrototypeEvent(id: "meeting-19", day: 19, time: "15:00", title: "Встреча с доверителем", caseNumber: "A-1234/2026", tone: .meeting),
        CalendarPrototypeEvent(id: "deadline-20", day: 20, time: "до 18:00", title: "Подать возражения", caseNumber: "A-1234/2026", tone: .deadline),
        CalendarPrototypeEvent(id: "filed-21", day: 21, time: "11:00", title: "Подача документа", caseNumber: "A-1234/2026", tone: .filed),
        CalendarPrototypeEvent(id: "task-22", day: 22, time: "до 16:00", title: "Подготовить ходатайство", caseNumber: "A-1234/2026", tone: .deadline),
        CalendarPrototypeEvent(id: "investigation-25", day: 25, time: "09:00", title: "Следственное действие", caseNumber: "A-1234/2026", tone: .investigation),
        CalendarPrototypeEvent(id: "fee-25", day: 25, time: "до 17:00", title: "Оплата госпошлины", caseNumber: "A-1234/2026", tone: .deadline),
        CalendarPrototypeEvent(id: "task-27", day: 27, time: "12:00", title: "Проверить приложения", caseNumber: "A-1234/2026", tone: .task),
        CalendarPrototypeEvent(id: "court-30", day: 30, time: "до 14:00", title: "Ответ на запрос суда", caseNumber: "A-1234/2026", tone: .deadline),
        CalendarPrototypeEvent(id: "complete-31", day: 31, time: "10:00", title: "Сверить позицию", caseNumber: "A-1234/2026", tone: .completed)
    ]

    private let deadlines = [
        CriticalDeadline(id: "critical-20", date: "До 20.05.2026", remaining: "2 дня", action: "Подать возражения", matter: "Дело A-1234/2026", urgent: true),
        CriticalDeadline(id: "critical-22", date: "До 22.05.2026", remaining: "4 дня", action: "Подготовить ходатайство", matter: "Дело A-1234/2026", urgent: false),
        CriticalDeadline(id: "critical-25", date: "До 25.05.2026", remaining: "7 дней", action: "Оплата госпошлины", matter: "Дело A-1234/2026", urgent: false),
        CriticalDeadline(id: "critical-30", date: "До 30.05.2026", remaining: "12 дней", action: "Ответ на запрос суда", matter: "Дело A-1234/2026", urgent: false)
    ]

    var body: some View {
        GeometryReader { proxy in
            HStack(spacing: 0) {
                canonicalSidebar
                    .frame(width: 200)
                VStack(spacing: 0) {
                    workspaceHeader
                        .frame(height: 70)
                    HStack(alignment: .top, spacing: 12) {
                        VStack(spacing: 10) {
                            caseSummary
                            calendarWorkspace
                        }
                        .frame(maxWidth: .infinity)
                        criticalRail
                            .frame(width: 270)
                    }
                    .padding(.horizontal, 14)
                    .padding(.bottom, 6)
                    footer
                        .frame(height: 30)
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            }
            .frame(width: max(proxy.size.width, 1200), height: max(proxy.size.height, 760), alignment: .topLeading)
            .background(background)
        }
        .frame(minWidth: 1200, idealWidth: 1536, minHeight: 760, idealHeight: 1024)
        .preferredColorScheme(.dark)
        .popover(item: $selectedEvent) { event in
            eventDetail(event)
                .frame(width: 280)
                .padding(14)
                .background(JafarPalette.background)
        }
        .onAppear(perform: startMotion)
    }

    private var background: some View {
        ZStack {
            LinearGradient(colors: [Color(red: 3 / 255, green: 7 / 255, blue: 14 / 255), JafarPalette.background], startPoint: .top, endPoint: .bottom)
            RadialGradient(colors: [JafarPalette.accentBlue.opacity(0.12), .clear], center: .center, startRadius: 40, endRadius: 650)
            RadialGradient(colors: [JafarPalette.goldGlow.opacity(0.10), .clear], center: .center, startRadius: 20, endRadius: 430)
            RadialGradient(colors: [.clear, .black.opacity(0.48)], center: .center, startRadius: 350, endRadius: 1000)
        }
        .ignoresSafeArea()
    }

    private var canonicalSidebar: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 8) {
                Image(systemName: "shield.lefthalf.filled").foregroundStyle(JafarPalette.accentGold)
                VStack(alignment: .leading, spacing: 1) {
                    Text("JAFAR AI").font(JusticeTypography.title).foregroundStyle(JafarPalette.textPrimary)
                    Text("ЮРИДИЧЕСКИЙ ПОМОЩНИК АДВОКАТА").font(.system(size: 9, weight: .medium, design: .rounded)).foregroundStyle(JafarPalette.textSecondary)
                }
            }
            .padding(.bottom, 7)

            ForEach([("Главная", "house.fill"), ("Дела", "briefcase.fill"), ("Календарь", "calendar"), ("Документы", "doc.text.fill"), ("Почта", "envelope.fill"), ("Правовой радар", "dot.radiowaves.left.and.right"), ("Практика", "books.vertical"), ("Черновики", "square.and.pencil"), ("Голосовые материалы", "waveform"), ("Аналитика", "chart.bar.xaxis"), ("Библиотека норм", "books.vertical.fill"), ("Проверка контрагентов", "person.crop.rectangle"), ("Настройки", "gearshape.fill")], id: \.0) { item in
                HStack(spacing: 8) { Image(systemName: item.1).frame(width: 16); Text(item.0).font(.system(size: 12, design: .rounded)); Spacer() }
                    .padding(.horizontal, 8).padding(.vertical, 5)
                    .foregroundStyle(item.0 == "Календарь" ? JafarPalette.accentGold : JafarPalette.textSecondary)
                    .background(item.0 == "Календарь" ? JafarPalette.accent.opacity(0.18) : .clear, in: RoundedRectangle(cornerRadius: 6))
                    .overlay(alignment: .leading) { Capsule().fill(item.0 == "Календарь" ? JafarPalette.accentGold : .clear).frame(width: 2, height: 18) }
            }
            Spacer(minLength: 4)
            CanonicalPanel { HStack(spacing: 8) { Circle().fill(JafarPalette.accentGold).frame(width: 26, height: 26).overlay(Text("ИИ").font(.caption).foregroundStyle(JafarPalette.background)); VStack(alignment: .leading, spacing: 2) { Text("Адвокат Иванов И.И.").font(.caption); Text("Демонстрационный контур").font(.caption2).foregroundStyle(JafarPalette.textMuted) } } }
            HStack(spacing: 6) { Circle().fill(JafarPalette.success).frame(width: 6, height: 6); VStack(alignment: .leading, spacing: 1) { Text("Система активна").font(.caption); Text("JAFAR AI · прототип календаря").font(.system(size: 9)).foregroundStyle(JafarPalette.textMuted) } }.padding(.horizontal, 6)
        }
        .padding(12)
        .background(Color.black.opacity(0.18))
    }

    private var workspaceHeader: some View {
        HStack(alignment: .center) {
            HStack(spacing: 6) {
                Text("Дела").font(.caption).foregroundStyle(JafarPalette.textSecondary)
                Image(systemName: "chevron.right").font(.caption2).foregroundStyle(JafarPalette.textMuted)
                Text("Дело A-1234/2026").font(.caption).foregroundStyle(JafarPalette.textSecondary)
                Image(systemName: "chevron.right").font(.caption2).foregroundStyle(JafarPalette.textMuted)
                Text("Календарь").font(.caption.weight(.semibold)).foregroundStyle(JafarPalette.accentGold)
            }
            Spacer()
            HStack(spacing: 8) {
                HStack { Image(systemName: "magnifyingglass"); Text("Поиск по делу"); Text("⌘K").font(JusticeTypography.mono) }.font(.caption2).foregroundStyle(JafarPalette.textMuted).padding(8).frame(width: 190).background(JafarPalette.surface, in: RoundedRectangle(cornerRadius: 6))
                Button { } label: { Image(systemName: "bell").overlay(alignment: .topTrailing) { Circle().fill(JafarPalette.danger).frame(width: 5, height: 5).offset(x: 3, y: -3) } }.buttonStyle(.plain).foregroundStyle(JafarPalette.accentGold)
                Button { } label: { Image(systemName: "gearshape") }.buttonStyle(.plain).foregroundStyle(JafarPalette.textSecondary)
            }
        }
        .padding(.horizontal, 16)
        .overlay(alignment: .bottom) { Rectangle().fill(JafarPalette.divider).frame(height: 1) }
    }

    private var caseSummary: some View {
        CanonicalPanel(glow: syncing ? JafarPalette.accentBlue : nil) {
            HStack(alignment: .center, spacing: 14) {
                VStack(alignment: .leading, spacing: 3) {
                    Text("Дело A-1234/2026").font(.system(size: 22, weight: .semibold, design: .serif))
                    Text("Павлик В.А.").font(.system(size: 14, weight: .medium, design: .serif)).foregroundStyle(JafarPalette.textSecondary)
                }
                Divider().frame(height: 34).overlay(JafarPalette.divider)
                Label("Арбитраж", systemImage: "building.columns").font(.caption).foregroundStyle(JafarPalette.textSecondary)
                Label("АС г. Москвы", systemImage: "mappin.and.ellipse").font(.caption).foregroundStyle(JafarPalette.textSecondary)
                Label("Высокий приоритет", systemImage: "exclamationmark.triangle.fill").font(.caption).foregroundStyle(JafarPalette.warning)
                Spacer()
                Text("В производстве").font(.caption.weight(.semibold)).foregroundStyle(JafarPalette.success).padding(.horizontal, 8).padding(.vertical, 5).background(JafarPalette.success.opacity(0.10), in: Capsule())
            }
        }
    }

    private var calendarWorkspace: some View {
        CanonicalPanel(glow: syncing ? JafarPalette.accentBlue : nil) {
            VStack(alignment: .leading, spacing: 10) {
                HStack {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Календарь процессуальных сроков").font(.system(size: 21, weight: .semibold, design: .serif))
                        Text("Май 2026 · Дело A-1234/2026").font(.caption).foregroundStyle(JafarPalette.textSecondary)
                    }
                    Spacer()
                    calendarControls
                }
                weekdayHeader
                monthGrid
            }
        }
        .frame(maxWidth: .infinity, minHeight: 600)
    }

    private var calendarControls: some View {
        HStack(spacing: 6) {
            Button("Сегодня") { withAnimation(reduceMotion ? nil : JafarMotion.normal) { selectedDay = 18 } }.buttonStyle(.bordered).controlSize(.small)
            Button { } label: { Image(systemName: "chevron.left") }.buttonStyle(.bordered).controlSize(.small)
            Button { } label: { Image(systemName: "chevron.right") }.buttonStyle(.bordered).controlSize(.small)
            Picker("Вид", selection: $calendarMode) { Text("Месяц").tag("Месяц"); Text("Неделя").tag("Неделя") }.pickerStyle(.segmented).frame(width: 112)
            Button("+ Добавить событие") { }.buttonStyle(.borderedProminent).controlSize(.small).tint(JafarPalette.accentGold)
            Button { beginSync() } label: { Image(systemName: syncing ? "arrow.triangle.2.circlepath.circle.fill" : "arrow.triangle.2.circlepath") }.buttonStyle(.bordered).controlSize(.small).foregroundStyle(syncing ? JafarPalette.accentBlue : JafarPalette.accentGold).rotationEffect(.degrees(syncTurn ? 360 : 0))
        }
    }

    private var weekdayHeader: some View {
        HStack(spacing: 4) {
            ForEach(["ПН", "ВТ", "СР", "ЧТ", "ПТ", "СБ", "ВС"], id: \.self) { day in
                Text(day).font(.caption.weight(.semibold)).foregroundStyle(day == "СБ" || day == "ВС" ? JafarPalette.textMuted : JafarPalette.textSecondary).frame(maxWidth: .infinity, alignment: .leading).padding(.leading, 6)
            }
        }
    }

    private var monthGrid: some View {
        let cells: [Int?] = [nil, nil, nil, nil, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, nil, nil, nil, nil, nil, nil]
        return LazyVGrid(columns: Array(repeating: GridItem(.flexible(), spacing: 4), count: 7), spacing: 4) {
            ForEach(Array(cells.enumerated()), id: \.offset) { _, day in
                calendarCell(day)
            }
        }
    }

    @ViewBuilder
    private func calendarCell(_ day: Int?) -> some View {
        if let day {
            let dayEvents = events.filter { $0.day == day }
            Button { withAnimation(reduceMotion ? nil : JafarMotion.normal) { selectedDay = day } } label: {
                VStack(alignment: .leading, spacing: 4) {
                    HStack {
                        Text("\(day)").font(day == 18 ? .system(size: 15, weight: .bold, design: .serif) : .system(size: 13, weight: .medium, design: .rounded)).foregroundStyle(day == 18 ? JafarPalette.accentGold : JafarPalette.textPrimary).frame(width: 24, height: 24).background(day == 18 ? JafarPalette.accentGold.opacity(0.12) : .clear, in: Circle()).overlay(Circle().stroke(day == 18 ? JafarPalette.accentGold.opacity(0.8) : .clear, lineWidth: 1))
                        Spacer()
                        if dayEvents.contains(where: { $0.tone == .deadline }) { Circle().fill(JafarPalette.warning).frame(width: 4, height: 4) }
                    }
                    ForEach(dayEvents.prefix(2)) { event in eventChip(event) }
                    Spacer(minLength: 0)
                }
                .padding(6)
                .frame(maxWidth: .infinity, minHeight: 76, alignment: .topLeading)
                .background(selectedDay == day ? JafarPalette.accent.opacity(0.11) : JafarPalette.surface.opacity(0.44), in: RoundedRectangle(cornerRadius: 6))
                .overlay(RoundedRectangle(cornerRadius: 6).stroke(selectedDay == day ? JafarPalette.accentGold.opacity(0.62) : JafarPalette.divider.opacity(0.70), lineWidth: selectedDay == day ? 1.2 : 0.6))
            }
            .buttonStyle(.plain)
        } else {
            Color.clear.frame(maxWidth: .infinity, minHeight: 76)
        }
    }

    private func eventChip(_ event: CalendarPrototypeEvent) -> some View {
        Button { selectedEvent = event } label: {
            HStack(spacing: 4) {
                Image(systemName: event.tone.symbol).font(.system(size: 7, weight: .bold))
                Text(event.time).font(.system(size: 8, weight: .semibold, design: .monospaced))
                Text(event.title).font(.system(size: 8, weight: .medium)).lineLimit(1)
            }
            .foregroundStyle(event.tone.color)
            .padding(.horizontal, 4).padding(.vertical, 3)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(event.tone.color.opacity(hoveredEventID == event.id ? 0.18 : 0.09), in: RoundedRectangle(cornerRadius: 4))
            .overlay(RoundedRectangle(cornerRadius: 4).stroke(event.tone.color.opacity(hoveredEventID == event.id ? 0.68 : 0.28), lineWidth: 0.6))
            .scaleEffect(hoveredEventID == event.id ? 1.015 : 1)
        }
        .buttonStyle(.plain)
        .onHover { hovering in withAnimation(JafarMotion.fast) { hoveredEventID = hovering ? event.id : nil } }
    }

    private var criticalRail: some View {
        VStack(spacing: 10) {
            CanonicalPanel(glow: urgentPulse ? JafarPalette.warning : nil) {
                VStack(alignment: .leading, spacing: 8) {
                    Label("КРИТИЧЕСКИЕ СРОКИ", systemImage: "exclamationmark.triangle.fill").font(.caption).foregroundStyle(JafarPalette.accentGold)
                    ForEach(deadlines) { deadline in deadlineRow(deadline) }
                }
            }
            CanonicalPanel {
                VStack(alignment: .leading, spacing: 7) {
                    Label("БЛИЖАЙШИЕ ЗАСЕДАНИЯ", systemImage: "building.columns").font(.caption).foregroundStyle(JafarPalette.accentGold)
                    hearingRow("18.05 · 10:30", "Арбитражный суд", "A-1234/2026", "Предварительное")
                    hearingRow("27.05 · 14:00", "АС г. Москвы", "A-1234/2026", "Основное")
                }
            }
            intelligencePanel
        }
    }

    private func deadlineRow(_ deadline: CriticalDeadline) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            HStack { Text(deadline.date).font(.caption2.monospacedDigit()).foregroundStyle(JafarPalette.accentGold); Spacer(); Text(deadline.remaining).font(.caption2.weight(.semibold)).foregroundStyle(deadline.urgent ? JafarPalette.warning : JafarPalette.textSecondary) }
            Text(deadline.action).font(.caption.weight(.semibold)).lineLimit(1)
            Text(deadline.matter).font(.caption2).foregroundStyle(JafarPalette.textMuted)
            Divider().overlay(JafarPalette.divider)
        }
        .padding(.vertical, deadline.urgent && urgentPulse ? 1 : 0)
        .background(deadline.urgent ? JafarPalette.warning.opacity(urgentPulse ? 0.08 : 0.03) : .clear, in: RoundedRectangle(cornerRadius: 5))
    }

    private func hearingRow(_ date: String, _ court: String, _ matter: String, _ type: String) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            HStack { Text(date).font(.caption2.monospacedDigit()); Spacer(); Text(type).font(.caption2).foregroundStyle(JafarPalette.accentGold) }
            Text(court).font(.caption).foregroundStyle(JafarPalette.textSecondary)
            Text(matter).font(.caption2).foregroundStyle(JafarPalette.textMuted)
        }
    }

    private var intelligencePanel: some View {
        CanonicalPanel(glow: syncing ? JafarPalette.accentBlue : nil) {
            VStack(alignment: .leading, spacing: 6) {
                HStack(spacing: 8) {
                    CanonicalIntelligenceEmblem(isAnalyzing: syncing, isListening: false, hasControlFocus: false, breathing: haloBreath, orbiting: ringTurn, sweeping: syncSweep, reduceMotion: reduceMotion)
                    VStack(alignment: .leading, spacing: 2) { Text("ЮСТИЦИЯ").font(JusticeTypography.title).foregroundStyle(JafarPalette.accentGold); Text("отслеживает сроки").font(.caption).foregroundStyle(JafarPalette.textSecondary) }
                }
                ForEach(["Критические сроки", "Возможные пересечения", "Процессуальные риски", "Подготовка к заседаниям"], id: \.self) { Label($0, systemImage: "checkmark").font(.caption2).foregroundStyle(JafarPalette.textSecondary) }
            }
        }
    }

    private var footer: some View {
        HStack(spacing: 16) { Label("Шифрование: активно", systemImage: "lock.fill"); Label("Календарь: демонстрационные данные", systemImage: "calendar"); Label("Синхронизация: локально", systemImage: "arrow.triangle.2.circlepath"); Spacer(); Text("JAFAR AI помогает контролировать процессуальные сроки") }
            .font(.caption2)
            .foregroundStyle(JafarPalette.textMuted)
            .padding(.horizontal, 14)
            .overlay(alignment: .top) { Rectangle().fill(JafarPalette.divider).frame(height: 1) }
    }

    private func eventDetail(_ event: CalendarPrototypeEvent) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Label(event.tone.label, systemImage: event.tone.symbol).font(.caption).foregroundStyle(event.tone.color)
            Text(event.title).font(.system(size: 19, weight: .semibold, design: .serif))
            Label("\(event.time) · 20.05.2026", systemImage: "clock").font(.caption).foregroundStyle(JafarPalette.textSecondary)
            Label(event.caseNumber, systemImage: "briefcase").font(.caption).foregroundStyle(JafarPalette.textSecondary)
            Text("Синтетическое событие демонстрационного прототипа.").font(.caption).foregroundStyle(JafarPalette.textMuted)
        }
    }

    private func startMotion() {
        guard !reduceMotion else { return }
        withAnimation(JafarMotion.ambient) { haloBreath = true }
        withAnimation(.linear(duration: 18).repeatForever(autoreverses: false)) { ringTurn = true }
        withAnimation(.easeInOut(duration: 2.8).repeatForever(autoreverses: true)) { syncSweep = true }
        withAnimation(.easeInOut(duration: 2.4).repeatForever(autoreverses: true)) { urgentPulse = true }
    }

    private func beginSync() {
        withAnimation(reduceMotion ? nil : JafarMotion.normal) { syncing = true }
        if !reduceMotion {
            withAnimation(.linear(duration: 1).repeatForever(autoreverses: false)) { syncTurn = true }
        }
        Task { @MainActor in
            try? await Task.sleep(for: .seconds(2))
            withAnimation(reduceMotion ? nil : JafarMotion.normal) {
                syncing = false
                syncTurn = false
            }
        }
    }
}

#Preview("Canonical JAFAR procedural calendar") {
    CanonicalCalendarPrototypeView()
}
