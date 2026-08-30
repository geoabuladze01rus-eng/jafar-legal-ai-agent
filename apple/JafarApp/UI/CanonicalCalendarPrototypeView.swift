import SwiftUI

struct CanonicalCalendarPrototypeView: View {
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    private let presentation: CalendarPresentation
    private let onRefresh: (@MainActor () async -> Void)?
    @State private var selectedDay: Int
    @State private var displayedMonth: Date
    @State private var hoveredEventID: String?
    @State private var selectedEvent: CalendarPresentationEvent?
    @State private var haloBreath = false
    @State private var ringTurn = false
    @State private var syncSweep = false
    @State private var syncing = false
    @State private var syncTurn = false
    @State private var calendarMode = "Месяц"
    @State private var urgentPulse = false
    @State private var showingAddEventNotice = false

    init(
        presentation: CalendarPresentation = .prototype,
        onRefresh: (@MainActor () async -> Void)? = nil
    ) {
        self.presentation = presentation
        self.onRefresh = onRefresh
        _displayedMonth = State(initialValue: presentation.initialMonth)
        _selectedDay = State(initialValue: Calendar.current.component(.day, from: presentation.initialMonth))
    }

    private var events: [CalendarPresentationEvent] { presentation.events }
    private var deadlines: [CalendarCriticalDeadline] {
        CalendarPresentationAdapter.criticalDeadlines(from: events, reference: timelineReferenceDate)
    }

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
        .alert("Добавление события", isPresented: $showingAddEventNotice) {
            Button("Понятно", role: .cancel) { }
        } message: {
            Text("Создание процессуальных событий будет доступно после подключения подтверждённого локального workflow. Событие не будет сохранено автоматически.")
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
            CanonicalPanel { HStack(spacing: 8) { Circle().fill(JafarPalette.accentGold).frame(width: 26, height: 26).overlay(Text("ИИ").font(.caption).foregroundStyle(JafarPalette.background)); VStack(alignment: .leading, spacing: 2) { Text("Адвокат").font(.caption); Text(isPrototype ? "Демонстрационный контур" : "Рабочий контур").font(.caption2).foregroundStyle(JafarPalette.textMuted) } } }
            HStack(spacing: 6) { Circle().fill(JafarPalette.success).frame(width: 6, height: 6); VStack(alignment: .leading, spacing: 1) { Text("Система активна").font(.caption); Text(isPrototype ? "JAFAR AI · прототип календаря" : "JAFAR AI · процессуальный календарь").font(.system(size: 9)).foregroundStyle(JafarPalette.textMuted) } }.padding(.horizontal, 6)
        }
        .padding(12)
        .background(Color.black.opacity(0.18))
    }

    private var workspaceHeader: some View {
        HStack(alignment: .center) {
            HStack(spacing: 6) {
                Text("Дела").font(.caption).foregroundStyle(JafarPalette.textSecondary)
                Image(systemName: "chevron.right").font(.caption2).foregroundStyle(JafarPalette.textMuted)
                Text(presentation.context.title).font(.caption).foregroundStyle(JafarPalette.textSecondary).lineLimit(1)
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
                    Text(presentation.context.title).font(.system(size: 22, weight: .semibold, design: .serif)).lineLimit(1)
                    Text(presentation.context.subtitle).font(.system(size: 14, weight: .medium, design: .serif)).foregroundStyle(JafarPalette.textSecondary).lineLimit(1)
                }
                Divider().frame(height: 34).overlay(JafarPalette.divider)
                Label(presentation.context.type ?? "Тип дела не указан", systemImage: "building.columns").font(.caption).foregroundStyle(JafarPalette.textSecondary)
                Label(presentation.context.court ?? "Суд не указан", systemImage: "mappin.and.ellipse").font(.caption).foregroundStyle(JafarPalette.textSecondary)
                Label(presentation.context.priority ?? "Приоритет не указан", systemImage: "exclamationmark.triangle.fill").font(.caption).foregroundStyle(presentation.context.priority == nil ? JafarPalette.textMuted : JafarPalette.warning)
                Spacer()
                Text(presentation.context.status ?? "Статус не указан").font(.caption.weight(.semibold)).foregroundStyle(presentation.context.status == nil ? JafarPalette.textMuted : JafarPalette.success).padding(.horizontal, 8).padding(.vertical, 5).background((presentation.context.status == nil ? JafarPalette.textMuted : JafarPalette.success).opacity(0.10), in: Capsule())
            }
        }
    }

    private var calendarWorkspace: some View {
        CanonicalPanel(glow: syncing ? JafarPalette.accentBlue : nil) {
            VStack(alignment: .leading, spacing: 10) {
                HStack {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Календарь процессуальных сроков").font(.system(size: 21, weight: .semibold, design: .serif))
                        Text("\(monthTitle) · \(presentation.context.title)").font(.caption).foregroundStyle(JafarPalette.textSecondary).lineLimit(1)
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

    private var isPrototype: Bool { presentation == .prototype }

    private var calendarModeSelection: Binding<String> {
        Binding(
            get: { calendarMode },
            set: { selection in
                if selection == "Месяц" { calendarMode = selection }
            }
        )
    }

    private var monthTitle: String {
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "ru_RU")
        formatter.dateFormat = "LLLL yyyy"
        return formatter.string(from: displayedMonth).capitalized
    }

    private var upcomingHearings: [CalendarPresentationEvent] {
        CalendarPresentationAdapter.upcomingHearings(from: events, reference: timelineReferenceDate)
    }

    private var timelineReferenceDate: Date { isPrototype ? presentation.initialMonth : .now }

    private var monthCells: [Int?] {
        let calendar = Calendar.current
        guard let monthStart = calendar.date(from: calendar.dateComponents([.year, .month], from: displayedMonth)),
              let dayRange = calendar.range(of: .day, in: .month, for: monthStart) else { return [] }
        let weekday = calendar.component(.weekday, from: monthStart)
        let leading = (weekday + 5) % 7
        var cells: [Int?] = Array(repeating: nil, count: leading)
        cells += dayRange.map { Optional($0) }
        let trailing = (7 - cells.count % 7) % 7
        cells += Array(repeating: nil, count: trailing)
        return cells
    }

    private func showToday() {
        withAnimation(reduceMotion ? nil : JafarMotion.normal) {
            displayedMonth = Calendar.current.date(from: Calendar.current.dateComponents([.year, .month], from: .now)) ?? .now
            selectedDay = Calendar.current.component(.day, from: .now)
        }
    }

    private func shiftMonth(by value: Int) {
        withAnimation(reduceMotion ? nil : JafarMotion.normal) {
            displayedMonth = Calendar.current.date(byAdding: .month, value: value, to: displayedMonth) ?? displayedMonth
            selectedDay = 1
        }
    }

    private func isCurrentDay(_ day: Int) -> Bool {
        if isPrototype { return day == 18 && Calendar.current.isDate(displayedMonth, equalTo: presentation.initialMonth, toGranularity: .month) }
        guard let date = Calendar.current.date(bySetting: .day, value: day, of: displayedMonth) else { return false }
        return Calendar.current.isDateInToday(date)
    }

    private func dueDateText(_ date: Date) -> String { "До \(fullDateText(date))" }

    private func shortDateText(_ date: Date) -> String {
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "ru_RU")
        formatter.dateFormat = "dd.MM"
        return formatter.string(from: date)
    }

    private func fullDateText(_ date: Date) -> String {
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "ru_RU")
        formatter.dateFormat = "dd.MM.yyyy"
        return formatter.string(from: date)
    }

    private var calendarControls: some View {
        HStack(spacing: 6) {
            Button("Сегодня") { showToday() }.buttonStyle(.bordered).controlSize(.small)
            Button { shiftMonth(by: -1) } label: { Image(systemName: "chevron.left") }.buttonStyle(.bordered).controlSize(.small)
            Button { shiftMonth(by: 1) } label: { Image(systemName: "chevron.right") }.buttonStyle(.bordered).controlSize(.small)
            Picker("Вид", selection: calendarModeSelection) {
                Text("Месяц").tag("Месяц")
                Text("Неделя").tag("Неделя").disabled(true)
            }
            .pickerStyle(.segmented)
            .frame(width: 112)
            .help("Недельный вид будет доступен после отдельной реализации.")
            .accessibilityHint("Неделя пока недоступна.")
            Button("+ Добавить событие") { showingAddEventNotice = true }.buttonStyle(.borderedProminent).controlSize(.small).tint(JafarPalette.accentGold)
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
        let cells = monthCells
        return LazyVGrid(columns: Array(repeating: GridItem(.flexible(), spacing: 4), count: 7), spacing: 4) {
            ForEach(Array(cells.enumerated()), id: \.offset) { _, day in
                calendarCell(day)
            }
        }
    }

    @ViewBuilder
    private func calendarCell(_ day: Int?) -> some View {
        if let day {
            let dayEvents = events.filter { Calendar.current.isDate($0.date, equalTo: displayedMonth, toGranularity: .month) && $0.day == day }
            Button { withAnimation(reduceMotion ? nil : JafarMotion.normal) { selectedDay = day } } label: {
                VStack(alignment: .leading, spacing: 4) {
                    HStack {
                        Text("\(day)").font(isCurrentDay(day) ? .system(size: 15, weight: .bold, design: .serif) : .system(size: 13, weight: .medium, design: .rounded)).foregroundStyle(isCurrentDay(day) ? JafarPalette.accentGold : JafarPalette.textPrimary).frame(width: 24, height: 24).background(isCurrentDay(day) ? JafarPalette.accentGold.opacity(0.12) : .clear, in: Circle()).overlay(Circle().stroke(isCurrentDay(day) ? JafarPalette.accentGold.opacity(0.8) : .clear, lineWidth: 1))
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

    private func eventChip(_ event: CalendarPresentationEvent) -> some View {
        Button { selectedEvent = event } label: {
            HStack(spacing: 4) {
                Image(systemName: event.tone.symbol).font(.system(size: 7, weight: .bold))
                if let time = event.time { Text(time).font(.system(size: 8, weight: .semibold, design: .monospaced)) }
                Text(event.title).font(.system(size: 8, weight: .medium)).lineLimit(1)
                if event.verification != .confirmed {
                    Text("Проверка").font(.system(size: 7, weight: .semibold)).lineLimit(1)
                    Image(systemName: event.verification.symbol ?? "eye.fill").font(.system(size: 7, weight: .bold))
                }
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
                    if deadlines.isEmpty {
                        Text("Критических сроков нет").font(.caption).foregroundStyle(JafarPalette.textMuted)
                    } else {
                        ForEach(deadlines) { deadline in deadlineRow(deadline) }
                    }
                }
            }
            CanonicalPanel {
                VStack(alignment: .leading, spacing: 7) {
                    Label("БЛИЖАЙШИЕ ЗАСЕДАНИЯ", systemImage: "building.columns").font(.caption).foregroundStyle(JafarPalette.accentGold)
                    if upcomingHearings.isEmpty {
                        Text("Ближайших заседаний нет").font(.caption).foregroundStyle(JafarPalette.textMuted)
                    } else {
                        ForEach(upcomingHearings) { hearingRow($0) }
                    }
                }
            }
            intelligencePanel
        }
    }

    private func deadlineRow(_ deadline: CalendarCriticalDeadline) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            HStack { Text(dueDateText(deadline.event.date)).font(.caption2.monospacedDigit()).foregroundStyle(JafarPalette.accentGold); Spacer(); Text(deadline.remaining).font(.caption2.weight(.semibold)).foregroundStyle(deadline.urgency.color) }
            Text(deadline.event.title).font(.caption.weight(.semibold)).lineLimit(1)
            Text(deadline.event.caseNumber ?? deadline.event.matter ?? "Дело не указано").font(.caption2).foregroundStyle(JafarPalette.textMuted).lineLimit(1)
            Divider().overlay(JafarPalette.divider)
        }
        .padding(.vertical, deadline.urgency == .critical && urgentPulse ? 1 : 0)
        .background(deadline.urgency == .critical ? JafarPalette.warning.opacity(urgentPulse ? 0.08 : 0.03) : .clear, in: RoundedRectangle(cornerRadius: 5))
    }

    private func hearingRow(_ hearing: CalendarPresentationEvent) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            HStack { Text("\(shortDateText(hearing.date))\(hearing.time.map { " · \($0)" } ?? "")").font(.caption2.monospacedDigit()); Spacer(); Text(hearing.verification.label ?? "Подтверждено").font(.caption2).foregroundStyle(JafarPalette.accentGold) }
            Text(hearing.court ?? "Суд не указан").font(.caption).foregroundStyle(JafarPalette.textSecondary).lineLimit(1)
            Text(hearing.caseNumber ?? hearing.matter ?? "Дело не указано").font(.caption2).foregroundStyle(JafarPalette.textMuted).lineLimit(1)
        }
    }

    private var intelligencePanel: some View {
        CanonicalPanel(glow: syncing ? JafarPalette.accentBlue : nil) {
            VStack(alignment: .leading, spacing: 6) {
                HStack(spacing: 8) {
                    CanonicalIntelligenceEmblem(isAnalyzing: syncing, isListening: false, hasControlFocus: false, breathing: haloBreath, orbiting: ringTurn, sweeping: syncSweep, reduceMotion: reduceMotion)
                    VStack(alignment: .leading, spacing: 2) { Text("ЮСТИЦИЯ").font(JusticeTypography.title).foregroundStyle(JafarPalette.accentGold); Text("отслеживает сроки").font(.caption).foregroundStyle(JafarPalette.textSecondary) }
                }
                ForEach(presentation.intelligenceItems, id: \.self) { Label($0, systemImage: "checkmark").font(.caption2).foregroundStyle(JafarPalette.textSecondary).lineLimit(1) }
            }
        }
    }

    private var footer: some View {
        HStack(spacing: 16) { Label("Шифрование: активно", systemImage: "lock.fill"); Label(isPrototype ? "Календарь: демонстрационные данные" : "Календарь: данные рабочей сводки", systemImage: "calendar"); Label(onRefresh == nil ? "Синхронизация: локально" : "Синхронизация: обновление сводки", systemImage: "arrow.triangle.2.circlepath"); Spacer(); Text("JAFAR AI помогает контролировать процессуальные сроки") }
            .font(.caption2)
            .foregroundStyle(JafarPalette.textMuted)
            .padding(.horizontal, 14)
            .overlay(alignment: .top) { Rectangle().fill(JafarPalette.divider).frame(height: 1) }
    }

    private func eventDetail(_ event: CalendarPresentationEvent) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Label(event.tone.label, systemImage: event.tone.symbol).font(.caption).foregroundStyle(event.tone.color)
            Text(event.title).font(.system(size: 19, weight: .semibold, design: .serif))
            Label("\(fullDateText(event.date))\(event.time.map { " · \($0)" } ?? "")", systemImage: "clock").font(.caption).foregroundStyle(JafarPalette.textSecondary)
            if let matter = event.caseNumber ?? event.matter { Label(matter, systemImage: "briefcase").font(.caption).foregroundStyle(JafarPalette.textSecondary) }
            if let court = event.court { Label(court, systemImage: "building.columns").font(.caption).foregroundStyle(JafarPalette.textSecondary) }
            if let source = event.source { Text(source).font(.caption).foregroundStyle(JafarPalette.textMuted).lineLimit(3) }
            if let verification = event.verification.label { Label(verification, systemImage: event.verification.symbol ?? "exclamationmark.shield.fill").font(.caption.weight(.semibold)).foregroundStyle(JafarPalette.warning) }
            if isPrototype { Text("Синтетическое событие демонстрационного прототипа.").font(.caption).foregroundStyle(JafarPalette.textMuted) }
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
            if let onRefresh { await onRefresh() }
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
