import SwiftUI
import UniformTypeIdentifiers

struct JusticiaHomeView: View {
    let navigate: (JusticiaSection) -> Void

    private let columns = [GridItem(.adaptive(minimum: 210), spacing: 14)]

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            pageHeader(
                title: "Добро пожаловать в «Юстицию»",
                subtitle: "Спокойная рабочая среда для дел, документов, сроков и локального ИИ."
            )

            LazyVGrid(columns: columns, spacing: 14) {
                quickAction("Создать документ", "doc.badge.plus", "Иск, жалоба, ходатайство", .documents)
                quickAction("Анализ документа", "doc.text.magnifyingglass", "Риски и рекомендации", .documents)
                quickAction("Добавить дело", "briefcase.fill", "Материалы и сроки", .matters)
                quickAction("Транскрибировать аудио", "waveform", "Запись в текст и факты", .transcription)
            }

            LazyVGrid(columns: columns, spacing: 14) {
                metricCard("Активные дела", "12", "+2 за неделю", "briefcase", JusticiaTheme.blue)
                metricCard("Ближайшие сроки", "3", "в течение 7 дней", "calendar.badge.exclamationmark", JusticiaTheme.red)
                metricCard("Документы", "47", "12 обработано ИИ", "doc.text", JusticiaTheme.blue)
                metricCard("ИИ-анализы", "26", "локально", "sparkles", JusticiaTheme.green)
            }

            HStack(alignment: .top, spacing: 14) {
                VStack(alignment: .leading, spacing: 12) {
                    sectionTitle("Последние дела", action: "Все дела") { navigate(.matters) }
                    ForEach(JusticiaDemoData.matters) { matter in
                        Button {
                            navigate(.matters)
                        } label: {
                            HStack(spacing: 12) {
                                JusticiaIconTile(systemName: "briefcase", color: JusticiaTheme.blue, size: 34)
                                VStack(alignment: .leading, spacing: 3) {
                                    Text(matter.number)
                                        .font(.subheadline.weight(.semibold))
                                        .foregroundStyle(JusticiaTheme.ink)
                                    Text(matter.title)
                                        .font(.caption)
                                        .foregroundStyle(JusticiaTheme.secondaryInk)
                                        .lineLimit(1)
                                }
                                Spacer()
                                JusticiaPill(text: matter.status, color: matter.status == "В работе" ? JusticiaTheme.green : JusticiaTheme.blue)
                            }
                            .padding(.vertical, 5)
                        }
                        .buttonStyle(.plain)
                    }
                }
                .justiciaCard()
                .frame(maxWidth: .infinity)

                VStack(alignment: .leading, spacing: 12) {
                    sectionTitle("Ближайшие сроки", action: "Календарь") { navigate(.deadlines) }
                    ForEach(JusticiaDemoData.deadlines) { item in
                        HStack(spacing: 12) {
                            VStack(spacing: 0) {
                                Text(item.day)
                                    .font(.headline.bold())
                                Text(item.month.uppercased())
                                    .font(.system(size: 9, weight: .bold))
                                    .foregroundStyle(JusticiaTheme.secondaryInk)
                            }
                            .frame(width: 42, height: 42)
                            .background(JusticiaTheme.blueSoft)
                            .clipShape(RoundedRectangle(cornerRadius: 10))

                            VStack(alignment: .leading, spacing: 3) {
                                Text(item.title)
                                    .font(.subheadline.weight(.semibold))
                                Text("Дело № " + item.matter)
                                    .font(.caption)
                                    .foregroundStyle(JusticiaTheme.secondaryInk)
                            }
                            Spacer()
                            JusticiaPill(text: item.urgency, color: JusticiaTheme.orange)
                        }
                    }
                }
                .justiciaCard()
                .frame(maxWidth: .infinity)
            }

            VStack(alignment: .leading, spacing: 12) {
                sectionTitle("Рекомендации «Юстиции»", action: "Открыть аналитику") { navigate(.analytics) }
                LazyVGrid(columns: columns, spacing: 12) {
                    recommendation("Проверить срок подачи апелляции", "calendar.badge.clock", JusticiaTheme.red)
                    recommendation("Дополнить доказательства перепиской", "paperclip", JusticiaTheme.orange)
                    recommendation("Сопоставить позицию с судебной практикой", "building.columns", JusticiaTheme.violet)
                }
            }
            .justiciaCard()
        }
    }

    private func quickAction(_ title: String, _ icon: String, _ subtitle: String, _ target: JusticiaSection) -> some View {
        Button {
            navigate(target)
        } label: {
            HStack(spacing: 12) {
                JusticiaIconTile(systemName: icon, color: JusticiaTheme.blue)
                VStack(alignment: .leading, spacing: 3) {
                    Text(title)
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(JusticiaTheme.ink)
                    Text(subtitle)
                        .font(.caption)
                        .foregroundStyle(JusticiaTheme.secondaryInk)
                }
                Spacer()
                Image(systemName: "chevron.right")
                    .font(.caption.bold())
                    .foregroundStyle(JusticiaTheme.secondaryInk.opacity(0.7))
            }
            .justiciaCard(padding: 14)
        }
        .buttonStyle(.plain)
    }

    private func metricCard(_ title: String, _ value: String, _ note: String, _ icon: String, _ color: Color) -> some View {
        VStack(alignment: .leading, spacing: 11) {
            HStack {
                JusticiaIconTile(systemName: icon, color: color)
                Spacer()
            }
            Text(value)
                .font(.system(size: 30, weight: .bold, design: .rounded))
                .foregroundStyle(JusticiaTheme.ink)
            Text(title)
                .font(.subheadline.weight(.semibold))
            Text(note)
                .font(.caption)
                .foregroundStyle(JusticiaTheme.secondaryInk)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .justiciaCard()
    }

    private func recommendation(_ text: String, _ icon: String, _ color: Color) -> some View {
        HStack(spacing: 10) {
            JusticiaIconTile(systemName: icon, color: color, size: 32)
            Text(text)
                .font(.subheadline)
                .foregroundStyle(JusticiaTheme.ink)
            Spacer()
        }
        .padding(12)
        .background(JusticiaTheme.surfaceMuted.opacity(0.75))
        .clipShape(RoundedRectangle(cornerRadius: 11))
    }
}

struct JusticiaMattersView: View {
    @State private var selectedMatter = JusticiaDemoData.matters[0]
    @State private var filter = ""

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            pageHeader(title: "Дела", subtitle: "Единая картина по материалам, участникам, событиям, рискам и срокам.")

            HStack(alignment: .top, spacing: 14) {
                VStack(alignment: .leading, spacing: 12) {
                    HStack {
                        Text("Мои дела")
                            .font(.headline)
                        Spacer()
                        Button {
                        } label: {
                            Label("Новое дело", systemImage: "plus")
                        }
                        .buttonStyle(.borderedProminent)
                    }

                    HStack {
                        Image(systemName: "magnifyingglass")
                            .foregroundStyle(JusticiaTheme.secondaryInk)
                        TextField("Поиск дела", text: $filter)
                            .textFieldStyle(.plain)
                    }
                    .padding(.horizontal, 11)
                    .frame(height: 36)
                    .background(JusticiaTheme.surfaceMuted)
                    .clipShape(RoundedRectangle(cornerRadius: 9))

                    ForEach(JusticiaDemoData.matters.filter { filter.isEmpty || $0.number.localizedCaseInsensitiveContains(filter) || $0.title.localizedCaseInsensitiveContains(filter) }) { matter in
                        Button {
                            selectedMatter = matter
                        } label: {
                            VStack(alignment: .leading, spacing: 8) {
                                HStack {
                                    Text(matter.number)
                                        .font(.subheadline.weight(.semibold))
                                    Spacer()
                                    JusticiaPill(text: matter.status, color: JusticiaTheme.green)
                                }
                                Text(matter.title)
                                    .font(.caption)
                                    .foregroundStyle(JusticiaTheme.secondaryInk)
                                    .multilineTextAlignment(.leading)
                                HStack {
                                    Text(matter.nextEvent)
                                    Spacer()
                                    Text("Риск: " + matter.risk)
                                }
                                .font(.caption2)
                                .foregroundStyle(JusticiaTheme.secondaryInk)
                            }
                            .padding(12)
                            .background(selectedMatter.id == matter.id ? JusticiaTheme.blueSoft : JusticiaTheme.surfaceMuted.opacity(0.55))
                            .clipShape(RoundedRectangle(cornerRadius: 11))
                        }
                        .buttonStyle(.plain)
                    }
                }
                .frame(width: 350)
                .justiciaCard()

                matterDetail
                    .frame(maxWidth: .infinity)
            }
        }
    }

    private var matterDetail: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: 5) {
                    HStack {
                        Text("№ " + selectedMatter.number)
                            .font(.title2.bold())
                        JusticiaPill(text: selectedMatter.status, color: JusticiaTheme.green)
                    }
                    Text(selectedMatter.title)
                        .font(.subheadline)
                        .foregroundStyle(JusticiaTheme.secondaryInk)
                }
                Spacer()
                Button("Добавить документ") { }
                    .buttonStyle(.borderedProminent)
            }

            Picker("Раздел", selection: .constant(0)) {
                Text("Обзор").tag(0)
                Text("Документы").tag(1)
                Text("Сроки").tag(2)
                Text("Участники").tag(3)
                Text("Аналитика ИИ").tag(4)
            }
            .pickerStyle(.segmented)

            HStack(alignment: .top, spacing: 14) {
                VStack(alignment: .leading, spacing: 11) {
                    Text("Основная информация")
                        .font(.headline)
                    detailRow("Суд", selectedMatter.court)
                    detailRow("Категория", "Взыскание задолженности")
                    detailRow("Цена иска", "12 500 000 ₽")
                    detailRow("Следующее событие", selectedMatter.nextEvent)
                    detailRow("Ответственный", "Юрист")
                }
                .justiciaCard()
                .frame(maxWidth: .infinity)

                VStack(alignment: .leading, spacing: 11) {
                    Text("Риски и контроль")
                        .font(.headline)
                    riskRow("Процессуальные сроки", "Средний", JusticiaTheme.orange)
                    riskRow("Доказательства", "Низкий", JusticiaTheme.green)
                    riskRow("Правовая позиция", "Средний", JusticiaTheme.orange)
                    riskRow("Текущие поручения", "3", JusticiaTheme.blue)
                }
                .justiciaCard()
                .frame(maxWidth: .infinity)
            }

            HStack(spacing: 12) {
                actionButton("Проанализировать дело", "sparkles", JusticiaTheme.blue)
                actionButton("Создать документ", "doc.badge.plus", JusticiaTheme.violet)
                actionButton("Добавить срок", "calendar.badge.plus", JusticiaTheme.orange)
            }
        }
        .justiciaCard()
    }

    private func detailRow(_ key: String, _ value: String) -> some View {
        HStack(alignment: .top) {
            Text(key)
                .foregroundStyle(JusticiaTheme.secondaryInk)
                .frame(width: 150, alignment: .leading)
            Text(value)
                .foregroundStyle(JusticiaTheme.ink)
            Spacer()
        }
        .font(.subheadline)
    }

    private func riskRow(_ title: String, _ value: String, _ color: Color) -> some View {
        HStack {
            Circle().fill(color).frame(width: 8, height: 8)
            Text(title).font(.subheadline)
            Spacer()
            JusticiaPill(text: value, color: color)
        }
    }
}

struct JusticiaDocumentsView: View {
    @State private var selected = JusticiaDemoData.documents[0]
    @State private var search = ""

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            pageHeader(title: "Документы", subtitle: "Материалы дела, ИИ-анализ, редактор и юридически значимые источники.")

            HStack(alignment: .top, spacing: 14) {
                VStack(alignment: .leading, spacing: 12) {
                    HStack {
                        Text("Документы дела")
                            .font(.headline)
                        Spacer()
                        Button {
                        } label: {
                            Label("Загрузить", systemImage: "square.and.arrow.down")
                        }
                        .buttonStyle(.borderedProminent)
                    }

                    HStack {
                        Image(systemName: "magnifyingglass")
                        TextField("Поиск по документам", text: $search)
                            .textFieldStyle(.plain)
                    }
                    .foregroundStyle(JusticiaTheme.secondaryInk)
                    .padding(.horizontal, 11)
                    .frame(height: 36)
                    .background(JusticiaTheme.surfaceMuted)
                    .clipShape(RoundedRectangle(cornerRadius: 9))

                    ForEach(JusticiaDemoData.documents.filter { search.isEmpty || $0.name.localizedCaseInsensitiveContains(search) }) { document in
                        Button {
                            selected = document
                        } label: {
                            HStack(spacing: 11) {
                                JusticiaIconTile(systemName: document.name.hasSuffix(".pdf") ? "doc.richtext" : "doc.text", color: document.name.hasSuffix(".pdf") ? JusticiaTheme.red : JusticiaTheme.blue, size: 34)
                                VStack(alignment: .leading, spacing: 3) {
                                    Text(document.name)
                                        .font(.subheadline.weight(.semibold))
                                        .foregroundStyle(JusticiaTheme.ink)
                                    Text(document.type + " · " + document.date)
                                        .font(.caption)
                                        .foregroundStyle(JusticiaTheme.secondaryInk)
                                }
                                Spacer()
                                JusticiaPill(text: document.aiStatus, color: document.aiStatus == "Готово" ? JusticiaTheme.green : JusticiaTheme.orange)
                            }
                            .padding(10)
                            .background(selected.id == document.id ? JusticiaTheme.blueSoft : Color.clear)
                            .clipShape(RoundedRectangle(cornerRadius: 10))
                        }
                        .buttonStyle(.plain)
                    }
                }
                .frame(width: 370)
                .justiciaCard()

                documentEditor
                    .frame(maxWidth: .infinity)
            }
        }
    }

    private var documentEditor: some View {
        VStack(spacing: 0) {
            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    Text(selected.name)
                        .font(.headline)
                    Text("Защищённая локальная копия")
                        .font(.caption)
                        .foregroundStyle(JusticiaTheme.secondaryInk)
                }
                Spacer()
                JusticiaPill(text: "Сохранено", color: JusticiaTheme.green)
                Button("Экспорт") { }.buttonStyle(.bordered)
                Button("Сохранить") { }.buttonStyle(.borderedProminent)
            }
            .padding(16)

            Divider()

            HStack(alignment: .top, spacing: 0) {
                VStack(alignment: .leading, spacing: 18) {
                    HStack(spacing: 12) {
                        ForEach(["B", "I", "U", "≡", "•"], id: \.self) { mark in
                            Button(mark) { }
                                .buttonStyle(.plain)
                                .foregroundStyle(JusticiaTheme.ink)
                        }
                    }
                    .padding(.bottom, 4)

                    Text("ИСКОВОЕ ЗАЯВЛЕНИЕ")
                        .font(.title3.bold())
                        .frame(maxWidth: .infinity, alignment: .center)

                    Text("1. Обстоятельства дела")
                        .font(.headline)
                    Text("Между сторонами заключён договор поставки. Представленные документы подтверждают передачу товара, возникновение обязательства и заявленный размер задолженности.")
                        .font(.body)
                        .lineSpacing(6)

                    Text("2. Правовое обоснование")
                        .font(.headline)
                    Text("Юстиция сопоставляет текст документа с материалами дела и отмечает места, требующие проверки правовых оснований, доказательств и процессуальных сроков.")
                        .font(.body)
                        .lineSpacing(6)

                    Spacer(minLength: 50)
                }
                .padding(24)
                .frame(maxWidth: .infinity, minHeight: 520, alignment: .topLeading)
                .background(Color.white)

                Divider()

                VStack(alignment: .leading, spacing: 14) {
                    HStack {
                        Image(systemName: "sparkles")
                            .foregroundStyle(JusticiaTheme.blue)
                        Text("ИИ-помощник")
                            .font(.headline)
                    }

                    Picker("", selection: .constant(0)) {
                        Text("Анализ").tag(0)
                        Text("Рекомендации").tag(1)
                    }
                    .pickerStyle(.segmented)

                    aiFinding("Структура документа", "Соответствует", JusticiaTheme.green)
                    aiFinding("Правовое основание", "Проверить 2 нормы", JusticiaTheme.orange)
                    aiFinding("Риски", "2 существенных", JusticiaTheme.red)
                    aiFinding("Судебная практика", "Найдено 8 актов", JusticiaTheme.blue)

                    Divider()

                    Text("Рекомендации")
                        .font(.subheadline.bold())
                    recommendationRow("Усилить правовое обоснование")
                    recommendationRow("Проверить расчёт неустойки")
                    recommendationRow("Добавить ссылки на доказательства")

                    Button {
                    } label: {
                        Label("Улучшить документ", systemImage: "wand.and.stars")
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.borderedProminent)

                    Spacer()
                }
                .padding(16)
                .frame(width: 300)\n                .frame(minHeight: 520, alignment: .top)
                .background(JusticiaTheme.surfaceMuted.opacity(0.55))
            }
        }
        .background(JusticiaTheme.surface)
        .clipShape(RoundedRectangle(cornerRadius: JusticiaTheme.corner))
        .overlay(RoundedRectangle(cornerRadius: JusticiaTheme.corner).stroke(JusticiaTheme.border))
    }

    private func aiFinding(_ title: String, _ value: String, _ color: Color) -> some View {
        HStack {
            Circle().fill(color).frame(width: 8, height: 8)
            Text(title).font(.caption)
            Spacer()
            Text(value).font(.caption.weight(.semibold)).foregroundStyle(color)
        }
    }

    private func recommendationRow(_ text: String) -> some View {
        HStack(alignment: .top, spacing: 8) {
            Image(systemName: "checkmark.circle")
                .foregroundStyle(JusticiaTheme.blue)
            Text(text)
                .font(.caption)
        }
    }
}

struct JusticiaAnalyticsView: View {
    private let columns = [GridItem(.adaptive(minimum: 220), spacing: 14)]

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            pageHeader(title: "Аналитика и отчёты", subtitle: "Риски, загрузка дел, динамика документов и выводы локального ИИ.")

            LazyVGrid(columns: columns, spacing: 14) {
                analyticsMetric("Всего дел", "26", "+10%", "briefcase", JusticiaTheme.blue)
                analyticsMetric("Активные", "18", "+25%", "checkmark.shield", JusticiaTheme.green)
                analyticsMetric("С риском", "6", "-14%", "exclamationmark.triangle", JusticiaTheme.orange)
                analyticsMetric("Средний срок", "42,5 дня", "-3,2%", "clock", JusticiaTheme.violet)
            }

            HStack(alignment: .top, spacing: 14) {
                VStack(alignment: .leading, spacing: 16) {
                    Text("Распределение рисков")
                        .font(.headline)

                    HStack(spacing: 24) {
                        ZStack {
                            Circle().stroke(JusticiaTheme.surfaceMuted, lineWidth: 22)
                            Circle()
                                .trim(from: 0, to: 0.62)
                                .stroke(JusticiaTheme.blue, style: StrokeStyle(lineWidth: 22, lineCap: .round))
                                .rotationEffect(.degrees(-90))
                            VStack {
                                Text("26").font(.title.bold())
                                Text("дел").font(.caption).foregroundStyle(JusticiaTheme.secondaryInk)
                            }
                        }
                        .frame(width: 150, height: 150)

                        VStack(alignment: .leading, spacing: 12) {
                            legend("Высокий риск", "22%", JusticiaTheme.red)
                            legend("Средний риск", "42%", JusticiaTheme.orange)
                            legend("Низкий риск", "27%", JusticiaTheme.green)
                            legend("Риск не выявлен", "9%", JusticiaTheme.blue)
                        }
                    }
                }
                .justiciaCard()
                .frame(maxWidth: .infinity)

                VStack(alignment: .leading, spacing: 16) {
                    Text("Динамика активности")
                        .font(.headline)
                    GeometryReader { proxy in
                        Path { path in
                            let points: [CGFloat] = [0.25, 0.40, 0.35, 0.56, 0.52, 0.70, 0.64, 0.82]
                            let width = proxy.size.width
                            let height = proxy.size.height
                            for index in points.indices {
                                let x = width * CGFloat(index) / CGFloat(points.count - 1)
                                let y = height * (1 - points[index])
                                if index == 0 { path.move(to: CGPoint(x: x, y: y)) }
                                else { path.addLine(to: CGPoint(x: x, y: y)) }
                            }
                        }
                        .stroke(JusticiaTheme.blue, style: StrokeStyle(lineWidth: 3, lineJoin: .round))
                    }
                    .frame(height: 155)

                    HStack {
                        Text("Документы")
                        Spacer()
                        Text("+18% за 6 месяцев")
                            .foregroundStyle(JusticiaTheme.green)
                    }
                    .font(.caption)
                }
                .justiciaCard()
                .frame(maxWidth: .infinity)
            }

            VStack(alignment: .leading, spacing: 12) {
                Text("Последние ИИ-анализы")
                    .font(.headline)
                ForEach(JusticiaDemoData.documents.prefix(4)) { document in
                    HStack {
                        JusticiaIconTile(systemName: "sparkles", color: JusticiaTheme.violet, size: 32)
                        VStack(alignment: .leading, spacing: 2) {
                            Text(document.name).font(.subheadline.weight(.semibold))
                            Text("Проверены структура, факты, риски и сроки").font(.caption).foregroundStyle(JusticiaTheme.secondaryInk)
                        }
                        Spacer()
                        JusticiaPill(text: document.aiStatus, color: JusticiaTheme.green)
                    }
                }
            }
            .justiciaCard()
        }
    }

    private func analyticsMetric(_ title: String, _ value: String, _ delta: String, _ icon: String, _ color: Color) -> some View {
        HStack {
            JusticiaIconTile(systemName: icon, color: color)
            VStack(alignment: .leading, spacing: 3) {
                Text(value).font(.title2.bold())
                Text(title).font(.caption).foregroundStyle(JusticiaTheme.secondaryInk)
            }
            Spacer()
            Text(delta).font(.caption.bold()).foregroundStyle(delta.hasPrefix("-") ? JusticiaTheme.green : color)
        }
        .justiciaCard()
    }

    private func legend(_ title: String, _ value: String, _ color: Color) -> some View {
        HStack {
            Circle().fill(color).frame(width: 9, height: 9)
            Text(title).font(.subheadline)
            Spacer()
            Text(value).font(.subheadline.weight(.semibold))
        }
        .frame(width: 220)
    }
}

struct JusticiaDeadlinesView: View {
    @State private var selectedDay = 20

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            pageHeader(title: "Сроки и календарь", subtitle: "Процессуальные события, напоминания и контроль просрочки.")

            HStack(alignment: .top, spacing: 14) {
                VStack(alignment: .leading, spacing: 16) {
                    HStack {
                        Button { } label: { Image(systemName: "chevron.left") }.buttonStyle(.bordered)
                        Text("Октябрь 2024").font(.title3.bold())
                        Button { } label: { Image(systemName: "chevron.right") }.buttonStyle(.bordered)
                        Spacer()
                        Picker("", selection: .constant(0)) {
                            Text("Месяц").tag(0)
                            Text("Неделя").tag(1)
                            Text("День").tag(2)
                        }
                        .pickerStyle(.segmented)
                        .frame(width: 250)
                    }

                    let days = Array(1...31)
                    LazyVGrid(columns: Array(repeating: GridItem(.flexible(), spacing: 6), count: 7), spacing: 7) {
                        ForEach(["Пн","Вт","Ср","Чт","Пт","Сб","Вс"], id: \.self) { day in
                            Text(day).font(.caption.bold()).foregroundStyle(JusticiaTheme.secondaryInk)
                        }
                        ForEach(days, id: \.self) { day in
                            Button {
                                selectedDay = day
                            } label: {
                                ZStack(alignment: .bottom) {
                                    Circle()
                                        .fill(selectedDay == day ? JusticiaTheme.blue : Color.clear)
                                        .frame(width: 34, height: 34)
                                    Text(String(day))
                                        .font(.caption.weight(selectedDay == day ? .bold : .regular))
                                        .foregroundStyle(selectedDay == day ? .white : JusticiaTheme.ink)
                                    if [5, 10, 13, 20, 22, 25].contains(day) {
                                        Circle()
                                            .fill(day == 20 ? JusticiaTheme.red : JusticiaTheme.orange)
                                            .frame(width: 5, height: 5)
                                            .offset(y: 4)
                                    }
                                }
                                .frame(height: 42)
                            }
                            .buttonStyle(.plain)
                        }
                    }
                }
                .justiciaCard()
                .frame(maxWidth: .infinity)

                VStack(alignment: .leading, spacing: 14) {
                    HStack {
                        Text("События на \(selectedDay) октября")
                            .font(.headline)
                        Spacer()
                        Button {
                        } label: { Image(systemName: "plus") }
                            .buttonStyle(.borderedProminent)
                    }

                    ForEach(JusticiaDemoData.deadlines) { item in
                        HStack(alignment: .top, spacing: 10) {
                            Circle().fill(item.title.contains("Суд") ? JusticiaTheme.red : JusticiaTheme.orange).frame(width: 9, height: 9).padding(.top, 5)
                            VStack(alignment: .leading, spacing: 3) {
                                Text(item.title).font(.subheadline.weight(.semibold))
                                Text("Дело № " + item.matter).font(.caption).foregroundStyle(JusticiaTheme.secondaryInk)
                            }
                            Spacer()
                        }
                    }

                    Divider()
                    Button {
                    } label: {
                        Label("Добавить срок", systemImage: "calendar.badge.plus")
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.bordered)
                }
                .justiciaCard()
                .frame(width: 360)
            }
        }
    }
}

struct JusticiaTemplatesView: View {
    @State private var category = "Все"
    private let categories = ["Все", "Гражданские", "Арбитражные", "Уголовные", "Договоры"]
    private let templates = [
        ("Исковое заявление", "doc.text", "Гражданский процесс"),
        ("Ходатайство", "doc.badge.plus", "Все виды судопроизводства"),
        ("Апелляционная жалоба", "arrow.up.doc", "Процессуальный документ"),
        ("Возражения на иск", "text.bubble", "Арбитражный процесс"),
        ("Договор поставки", "doc.on.clipboard", "Коммерческий договор"),
        ("Претензия", "envelope", "Досудебный порядок"),
        ("Кассационная жалоба", "building.columns", "Процессуальный документ"),
        ("Акт приёма-передачи", "checkmark.square", "Приложение к договору")
    ]

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            pageHeader(title: "Шаблоны документов", subtitle: "Проверенные основы документов с возможностью доработки локальным ИИ.")

            HStack {
                Picker("Категория", selection: $category) {
                    ForEach(categories, id: \.self) { Text($0).tag($0) }
                }
                .pickerStyle(.segmented)
                Spacer()
                Button {
                } label: {
                    Label("Создать шаблон", systemImage: "plus")
                }
                .buttonStyle(.borderedProminent)
            }

            LazyVGrid(columns: [GridItem(.adaptive(minimum: 230), spacing: 14)], spacing: 14) {
                ForEach(Array(templates.enumerated()), id: \.offset) { index, item in
                    VStack(alignment: .leading, spacing: 14) {
                        HStack {
                            JusticiaIconTile(systemName: item.1, color: JusticiaTheme.blue)
                            Spacer()
                            Button {
                            } label: {
                                Image(systemName: index < 3 ? "star.fill" : "star")
                                    .foregroundStyle(JusticiaTheme.gold)
                            }
                            .buttonStyle(.plain)
                        }
                        Text(item.0).font(.headline)
                        Text(item.2).font(.caption).foregroundStyle(JusticiaTheme.secondaryInk)
                        Spacer()
                        Button("Использовать") { }
                            .buttonStyle(.bordered)
                            .frame(maxWidth: .infinity, alignment: .trailing)
                    }
                    .frame(minHeight: 150, alignment: .topLeading)
                    .justiciaCard()
                }
            }
        }
    }
}

struct JusticiaPublishingView: View {
    @State private var tab = 0

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            pageHeader(title: "Автопубликации", subtitle: "Редакционная очередь юридического контента с обязательной проверкой перед отправкой.")

            HStack {
                Picker("", selection: $tab) {
                    Text("Публикации").tag(0)
                    Text("Планирование").tag(1)
                    Text("Аналитика").tag(2)
                }
                .pickerStyle(.segmented)
                .frame(width: 360)
                Spacer()
                Button {
                } label: {
                    Label("Создать публикацию", systemImage: "plus")
                }
                .buttonStyle(.borderedProminent)
            }

            VStack(spacing: 0) {
                publishingHeader
                Divider()
                publishingRow("Как защитить свои права", "Опубликовано", "12.12.2024", JusticiaTheme.green)
                Divider()
                publishingRow("Пять ошибок в договоре", "На проверке", "15.12.2024", JusticiaTheme.orange)
                Divider()
                publishingRow("Судебная практика недели", "Черновик", "18.12.2024", JusticiaTheme.violet)
                Divider()
                publishingRow("Изменения в законодательстве", "Опубликовано", "10.12.2024", JusticiaTheme.green)
            }
            .justiciaCard(padding: 0)

            HStack(spacing: 14) {
                statusInfo("Человеческая проверка", "Обязательна перед публикацией", "person.badge.shield.checkmark", JusticiaTheme.blue)
                statusInfo("Защита от дублей", "Неоднозначная отправка блокирует повтор", "checkmark.circle", JusticiaTheme.green)
                statusInfo("ИИ-черновики", "Всегда начинают со статуса «На проверке»", "sparkles", JusticiaTheme.orange)
            }
        }
    }

    private var publishingHeader: some View {
        HStack {
            Text("Тема").frame(maxWidth: .infinity, alignment: .leading)
            Text("Статус").frame(width: 130, alignment: .leading)
            Text("Дата").frame(width: 120, alignment: .leading)
            Text("Канал").frame(width: 100, alignment: .leading)
        }
        .font(.caption.bold())
        .foregroundStyle(JusticiaTheme.secondaryInk)
        .padding(14)
    }

    private func publishingRow(_ title: String, _ status: String, _ date: String, _ color: Color) -> some View {
        HStack {
            Text(title).font(.subheadline.weight(.semibold)).frame(maxWidth: .infinity, alignment: .leading)
            JusticiaPill(text: status, color: color).frame(width: 130, alignment: .leading)
            Text(date).font(.caption).frame(width: 120, alignment: .leading)
            Label("Telegram", systemImage: "paperplane.fill").font(.caption).frame(width: 100, alignment: .leading)
        }
        .padding(14)
    }

    private func statusInfo(_ title: String, _ text: String, _ icon: String, _ color: Color) -> some View {
        HStack(spacing: 12) {
            JusticiaIconTile(systemName: icon, color: color)
            VStack(alignment: .leading, spacing: 3) {
                Text(title).font(.subheadline.weight(.semibold))
                Text(text).font(.caption).foregroundStyle(JusticiaTheme.secondaryInk)
            }
            Spacer()
        }
        .justiciaCard()
        .frame(maxWidth: .infinity)
    }
}

struct JusticiaTranscriptionView: View {
    @ObservedObject var voice: VoiceSessionViewModel
    @State private var showingImporter = false
    @State private var importedAudioName: String?
    @State private var selectedTab = 0
    @State private var isAutoSaveEnabled = true

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            pageHeader(title: "Транскрибация аудио", subtitle: "Расшифровка переговоров, допросов, консультаций и судебных записей.")

            HStack(alignment: .top, spacing: 14) {
                VStack(spacing: 14) {
                    audioPlayerCard

                    Picker("", selection: $selectedTab) {
                        Text("Транскрипт").tag(0)
                        Text("Краткое резюме").tag(1)
                        Text("Ключевые фрагменты").tag(2)
                        Text("Поручения").tag(3)
                    }
                    .pickerStyle(.segmented)

                    transcriptionBody
                }
                .frame(maxWidth: .infinity)

                VStack(spacing: 14) {
                    summaryCard
                    factsCard
                    actionsCard
                }
                .frame(width: 340)
            }
        }
        .fileImporter(isPresented: $showingImporter, allowedContentTypes: [.audio], allowsMultipleSelection: false) { result in
            if case .success(let urls) = result, let url = urls.first {
                importedAudioName = url.lastPathComponent
            }
        }
    }

    private var audioPlayerCard: some View {
        VStack(spacing: 16) {
            HStack {
                JusticiaIconTile(systemName: "waveform", color: JusticiaTheme.blue)
                VStack(alignment: .leading, spacing: 3) {
                    Text(importedAudioName ?? "Запись встречи")
                        .font(.headline)
                    Text(importedAudioName == nil ? "Выберите аудиофайл или начните запись" : "Файл выбран · готов к обработке")
                        .font(.caption)
                        .foregroundStyle(JusticiaTheme.secondaryInk)
                }
                Spacer()
                Button {
                    showingImporter = true
                } label: {
                    Label("Загрузить аудио", systemImage: "square.and.arrow.down")
                }
                .buttonStyle(.bordered)

                Button {
                    Task {
                        if voice.isListening { await voice.stopAndSend() }
                        else { await voice.start() }
                    }
                } label: {
                    Label(voice.isListening ? "Остановить" : "Запись", systemImage: voice.isListening ? "stop.circle.fill" : "record.circle")
                }
                .buttonStyle(.borderedProminent)
                .disabled(voice.isSending)
            }

            HStack(alignment: .center, spacing: 3) {
                ForEach(0..<72, id: \.self) { index in
                    Capsule()
                        .fill(index < 34 ? JusticiaTheme.blue : JusticiaTheme.blue.opacity(0.20))
                        .frame(width: 3, height: CGFloat(10 + (index * 13) % 35))
                }
            }
            .frame(maxWidth: .infinity, minHeight: 48)

            HStack {
                Button {
                } label: { Image(systemName: "gobackward.10") }.buttonStyle(.plain)
                Button {
                } label: { Image(systemName: "play.fill") }.buttonStyle(.borderedProminent)
                Button {
                } label: { Image(systemName: "goforward.10") }.buttonStyle(.plain)
                Text("00:12:34 / 01:02:18")
                    .font(.caption.monospacedDigit())
                    .foregroundStyle(JusticiaTheme.secondaryInk)
                Spacer()
                Text("1.0×").font(.caption.bold())
                Image(systemName: "speaker.wave.2").foregroundStyle(JusticiaTheme.secondaryInk)
            }
        }
        .justiciaCard()
    }

    @ViewBuilder
    private var transcriptionBody: some View {
        switch selectedTab {
        case 1:
            VStack(alignment: .leading, spacing: 12) {
                Text("Краткое резюме").font(.headline)
                Text(voice.response.isEmpty ? "После обработки «Юстиция» сформирует сжатое резюме беседы, отделит установленные факты от предположений и выделит вопросы, требующие проверки." : voice.response)
                    .font(.body)
                    .lineSpacing(6)
            }
            .frame(maxWidth: .infinity, minHeight: 360, alignment: .topLeading)
            .justiciaCard()
        case 2:
            VStack(alignment: .leading, spacing: 12) {
                Text("Ключевые фрагменты").font(.headline)
                fragment("00:02:10", "Порядок подписания актов", JusticiaTheme.blue)
                fragment("00:15:43", "Упоминание суммы договора", JusticiaTheme.orange)
                fragment("00:37:21", "Возможное противоречие в показаниях", JusticiaTheme.red)
                fragment("01:02:17", "Роль технического специалиста", JusticiaTheme.violet)
            }
            .frame(maxWidth: .infinity, minHeight: 360, alignment: .topLeading)
            .justiciaCard()
        case 3:
            VStack(alignment: .leading, spacing: 12) {
                Text("Поручения").font(.headline)
                task("Запросить документы у контрагента", "21 окт.")
                task("Проверить полномочия специалиста", "25 окт.")
                task("Подготовить вопросы к повторному допросу", "28 окт.")
            }
            .frame(maxWidth: .infinity, minHeight: 360, alignment: .topLeading)
            .justiciaCard()
        default:
            VStack(alignment: .leading, spacing: 0) {
                transcriptRow("00:00:12", "Юрист", "Добрый день. Зафиксируем основные обстоятельства и последовательность событий.", JusticiaTheme.blue)
                Divider()
                transcriptRow("00:00:28", "Клиент", "Договор был заключён в октябре. Работы выполнялись поэтапно, документы передавались представителю заказчика.", JusticiaTheme.orange)
                Divider()
                transcriptRow("00:01:05", "Юрист", "Какие документы подтверждают выполнение работ и кто подписывал акты?", JusticiaTheme.blue)
                Divider()
                transcriptRow("00:02:10", "Клиент", "Акты подписывались на основании документов подрядчика. Насколько я помню, замечаний по объёму не было.", JusticiaTheme.orange)

                if !voice.transcript.isEmpty {
                    Divider()
                    transcriptRow("сейчас", "Вы", voice.transcript, JusticiaTheme.green)
                }
            }
            .justiciaCard(padding: 0)
        }
    }

    private var summaryCard: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                JusticiaIconTile(systemName: "sparkles", color: JusticiaTheme.violet, size: 32)
                Text("Сводка ИИ").font(.headline)
            }
            Text("Выделены участники, ключевые обстоятельства, документы, возможные противоречия и действия, которые стоит проверить.")
                .font(.caption)
                .foregroundStyle(JusticiaTheme.secondaryInk)
                .lineSpacing(4)
            Button("Сформировать справку") { }
                .buttonStyle(.bordered)
        }
        .justiciaCard()
    }

    private var factsCard: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Извлечённые факты").font(.headline)
            fact("Договор заключён сторонами", true)
            fact("Акты подписывались представителем", true)
            fact("Личный выезд на объект не подтверждён", false)
            fact("Требуется сверка полномочий", false)
        }
        .justiciaCard()
    }

    private var actionsCard: some View {
        VStack(alignment: .leading, spacing: 10) {
            Toggle("Сохранять заметку в дело", isOn: $isAutoSaveEnabled)
            Button {
            } label: {
                Label("Сохранить транскрипт", systemImage: "square.and.arrow.down")
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(.borderedProminent)
            if voice.approvalRequired {
                HStack {
                    Button("Отмена") { voice.cancelPendingCommand() }.buttonStyle(.bordered)
                    Button("Подтвердить") { Task { await voice.confirmPendingCommand() } }.buttonStyle(.borderedProminent)
                }
            }
            if let error = voice.errorMessage {
                Text(error).font(.caption).foregroundStyle(JusticiaTheme.red)
            }
        }
        .justiciaCard()
    }

    private func transcriptRow(_ time: String, _ speaker: String, _ text: String, _ color: Color) -> some View {
        HStack(alignment: .top, spacing: 12) {
            Text(time)
                .font(.caption.monospacedDigit())
                .foregroundStyle(JusticiaTheme.secondaryInk)
                .frame(width: 70, alignment: .leading)
            Circle().fill(color.opacity(0.15)).frame(width: 28, height: 28).overlay(Image(systemName: "person.fill").font(.caption).foregroundStyle(color))
            Text(speaker)
                .font(.caption.weight(.semibold))
                .frame(width: 72, alignment: .leading)
            Text(text)
                .font(.subheadline)
                .foregroundStyle(JusticiaTheme.ink)
            Spacer()
        }
        .padding(13)
    }

    private func fragment(_ time: String, _ text: String, _ color: Color) -> some View {
        HStack {
            Circle().fill(color).frame(width: 8, height: 8)
            Text(time).font(.caption.monospacedDigit()).foregroundStyle(JusticiaTheme.secondaryInk)
            Text(text).font(.subheadline)
            Spacer()
            Image(systemName: "bookmark").foregroundStyle(JusticiaTheme.secondaryInk)
        }
        .padding(.vertical, 5)
    }

    private func task(_ text: String, _ date: String) -> some View {
        HStack {
            Image(systemName: "square").foregroundStyle(JusticiaTheme.secondaryInk)
            Text(text).font(.subheadline)
            Spacer()
            Text(date).font(.caption).foregroundStyle(JusticiaTheme.red)
        }
    }

    private func fact(_ text: String, _ confirmed: Bool) -> some View {
        HStack(alignment: .top, spacing: 8) {
            Image(systemName: confirmed ? "checkmark.circle.fill" : "exclamationmark.circle.fill")
                .foregroundStyle(confirmed ? JusticiaTheme.green : JusticiaTheme.orange)
            Text(text).font(.caption)
        }
    }
}

struct JusticiaSettingsView: View {
    @State private var accent = 0
    @State private var interfaceSize = 1
    @State private var notifications = true
    @State private var compactSidebar = false
    @State private var showHints = true

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            pageHeader(title: "Настройки", subtitle: "Персонализация, локальный ИИ, уведомления и параметры рабочего пространства.")

            HStack(alignment: .top, spacing: 14) {
                VStack(alignment: .leading, spacing: 16) {
                    Text("Профиль")
                        .font(.headline)
                    HStack(spacing: 14) {
                        Circle().fill(JusticiaTheme.blueSoft).frame(width: 64, height: 64)
                            .overlay(Image(systemName: "person.fill").font(.title).foregroundStyle(JusticiaTheme.blue))
                        VStack(alignment: .leading, spacing: 4) {
                            Text("Профиль юриста").font(.title3.bold())
                            Text("Локальное рабочее пространство").font(.caption).foregroundStyle(JusticiaTheme.secondaryInk)
                        }
                    }
                    Divider()
                    Label("Данные приложения хранятся локально и шифруются.", systemImage: "lock.shield")
                        .font(.caption)
                        .foregroundStyle(JusticiaTheme.secondaryInk)
                }
                .justiciaCard()
                .frame(maxWidth: .infinity)

                VStack(alignment: .leading, spacing: 14) {
                    Text("Интерфейс")
                        .font(.headline)
                    Text("Тема")
                        .font(.caption.weight(.semibold))
                    HStack {
                        themeOption("Светлая", selected: accent == 0) { accent = 0 }
                        themeOption("Системная", selected: accent == 1) { accent = 1 }
                    }

                    Text("Размер интерфейса")
                        .font(.caption.weight(.semibold))
                    Picker("", selection: $interfaceSize) {
                        Text("Компактный").tag(0)
                        Text("Стандартный").tag(1)
                        Text("Крупный").tag(2)
                    }
                    .pickerStyle(.segmented)

                    Toggle("Показывать подсказки ИИ", isOn: $showHints)
                    Toggle("Компактная боковая панель", isOn: $compactSidebar)
                    Toggle("Системные уведомления", isOn: $notifications)
                }
                .justiciaCard()
                .frame(maxWidth: .infinity)
            }

            #if os(macOS)
            VStack(alignment: .leading, spacing: 12) {
                Text("Локальный ИИ")
                    .font(.headline)
                LocalAIStatusView()
            }
            .justiciaCard()
            #endif

            VStack(alignment: .leading, spacing: 12) {
                Text("Безопасность")
                    .font(.headline)
                settingsRow("Локальное шифрование", "Включено", "lock.fill", JusticiaTheme.green)
                settingsRow("Облачная отправка конфиденциальных данных", "Выключена", "icloud.slash", JusticiaTheme.green)
                settingsRow("Защищённый локальный API", "Включён", "network.badge.shield.half.filled", JusticiaTheme.green)
            }
            .justiciaCard()
        }
    }

    private func themeOption(_ title: String, selected: Bool, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            VStack(spacing: 7) {
                RoundedRectangle(cornerRadius: 8)
                    .fill(selected ? JusticiaTheme.blueSoft : JusticiaTheme.surfaceMuted)
                    .frame(height: 54)
                    .overlay(RoundedRectangle(cornerRadius: 8).stroke(selected ? JusticiaTheme.blue : JusticiaTheme.border, lineWidth: selected ? 2 : 1))
                Text(title).font(.caption.weight(.semibold)).foregroundStyle(JusticiaTheme.ink)
            }
        }
        .buttonStyle(.plain)
        .frame(maxWidth: .infinity)
    }

    private func settingsRow(_ title: String, _ status: String, _ icon: String, _ color: Color) -> some View {
        HStack {
            JusticiaIconTile(systemName: icon, color: color, size: 32)
            Text(title).font(.subheadline)
            Spacer()
            JusticiaPill(text: status, color: color)
        }
    }
}

// MARK: - Shared helpers

@ViewBuilder
func pageHeader(title: String, subtitle: String) -> some View {
    VStack(alignment: .leading, spacing: 5) {
        Text(title)
            .font(.system(size: 28, weight: .bold, design: .rounded))
            .foregroundStyle(JusticiaTheme.ink)
        Text(subtitle)
            .font(.subheadline)
            .foregroundStyle(JusticiaTheme.secondaryInk)
    }
    .frame(maxWidth: .infinity, alignment: .leading)
}

@ViewBuilder
func sectionTitle(_ title: String, action: String, handler: @escaping () -> Void) -> some View {
    HStack {
        Text(title)
            .font(.headline)
        Spacer()
        Button(action, action: handler)
            .font(.caption.weight(.semibold))
            .buttonStyle(.plain)
            .foregroundStyle(JusticiaTheme.blue)
    }
}

@ViewBuilder
func actionButton(_ title: String, _ icon: String, _ color: Color) -> some View {
    Button {
    } label: {
        Label(title, systemImage: icon)
            .font(.subheadline.weight(.semibold))
            .foregroundStyle(color)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 10)
            .background(color.opacity(0.08))
            .clipShape(RoundedRectangle(cornerRadius: 10))
    }
    .buttonStyle(.plain)
}