import SwiftUI

private enum JafarPalette {
    static let background = Color(red: 0.055, green: 0.06, blue: 0.07)
    static let panel = Color(red: 0.10, green: 0.105, blue: 0.115)
    static let elevated = Color(red: 0.14, green: 0.14, blue: 0.15)
    static let gold = Color(red: 0.78, green: 0.62, blue: 0.30)
    static let mutedGold = Color(red: 0.56, green: 0.43, blue: 0.22)
    static let text = Color(red: 0.92, green: 0.90, blue: 0.86)
    static let secondary = Color(red: 0.62, green: 0.62, blue: 0.60)
    static let border = Color.white.opacity(0.10)
}

private struct DashboardCard<Content: View>: View {
    let title: String
    @ViewBuilder var content: Content
    var body: some View { VStack(alignment: .leading, spacing: 14) { Text(title.uppercased()).font(.caption.weight(.semibold)).tracking(1.2).foregroundStyle(JafarPalette.secondary); content }.padding(18).background(JafarPalette.panel, in: RoundedRectangle(cornerRadius: 14)).overlay(RoundedRectangle(cornerRadius: 14).stroke(JafarPalette.border)) }
}

struct ContentView: View {
    @EnvironmentObject private var localBackend: LocalBackendManager
    @StateObject private var voice = VoiceSessionViewModel(commandClient: JafarClientConfiguration.makeCommandClient(), userId: "local-user")
    @State private var commandText = ""
    @State private var selected = "Главная"
    private let navigation = ["Главная", "Дела", "Календарь", "Документы", "Почта", "Правовой радар", "Практика", "Черновики", "Голосовые материалы", "Аналитика", "Библиотека норм", "Проверка контрагентов", "Настройки"]

    var body: some View {
        NavigationSplitView { sidebar } detail: { dashboard }
            .preferredColorScheme(.dark)
            .onChange(of: localBackend.state) { _, _ in voice.configure(commandClient: JafarClientConfiguration.makeCommandClient()) }
    }
    private var sidebar: some View { VStack(alignment: .leading, spacing: 10) { VStack(alignment: .leading, spacing: 3) { Text("JAFAR AI").font(.title3.weight(.bold)).foregroundStyle(JafarPalette.gold); Text("Юридический помощник адвоката").font(.caption).foregroundStyle(JafarPalette.secondary) }.padding(.bottom, 16); ForEach(navigation, id: \.self) { item in Button { selected = item } label: { Label(item, systemImage: icon(for: item)).frame(maxWidth: .infinity, alignment: .leading) }.buttonStyle(.plain).padding(.vertical, 7).padding(.horizontal, 9).background(selected == item ? JafarPalette.mutedGold.opacity(0.28) : .clear, in: RoundedRectangle(cornerRadius: 8)).foregroundStyle(selected == item ? JafarPalette.gold : JafarPalette.text) }; Spacer(); Label(backendStatus, systemImage: backendSymbol).font(.caption).foregroundStyle(backendColor) }.padding(18).frame(minWidth: 220).background(JafarPalette.background) }
    private var dashboard: some View { ScrollView { VStack(alignment: .leading, spacing: 22) { HStack(alignment: .top) { VStack(alignment: .leading, spacing: 5) { Text("Доброе утро").font(.largeTitle.weight(.bold)).foregroundStyle(JafarPalette.text); Text("JAFAR AI готов служить вашей практике").foregroundStyle(JafarPalette.secondary) }; Spacer(); Button("＋ Создать") {}.buttonStyle(.bordered).tint(JafarPalette.gold) }; TextField("Поиск по делам, документам, правовым позициям…", text: .constant("")).textFieldStyle(.roundedBorder).disabled(true); JusticeHeroView(); JafarCommandBar(text: $commandText, voice: voice, send: sendCommand); LazyVGrid(columns: [GridItem(.adaptive(minimum: 180), spacing: 12)], spacing: 12) { ForEach(["Что требует моего внимания?", "Разбери последнее письмо", "Что нового по делу Павлика?", "Подготовь правовую позицию"], id: \.self) { quick in Button { commandText = quick } label: { Text(quick).frame(maxWidth: .infinity, alignment: .leading).padding(13).background(JafarPalette.elevated, in: RoundedRectangle(cornerRadius: 10)) }.buttonStyle(.plain).foregroundStyle(JafarPalette.text) } }; HStack(alignment: .top, spacing: 16) { VStack(spacing: 16) { FocusDayView(); MattersOverviewView(); JafarActivityView() }.frame(maxWidth: .infinity); VStack(spacing: 16) { TasksDeadlinesView(); UpcomingHearingsView(); LegalRadarView(); AIAnalyticsView(); VoiceMaterialsSummaryView() }.frame(width: 300) } }.padding(28).frame(maxWidth: 1200, alignment: .leading) }.background(JafarPalette.background) }
    private func sendCommand() { let text = commandText.trimmingCharacters(in: .whitespacesAndNewlines); guard !text.isEmpty else { return }; Task { await voice.send(text: text) } }
    private var backendStatus: String { if case .running = localBackend.state { return "Джафар готов" }; if case .starting = localBackend.state { return "Backend запускается" }; return "Backend недоступен" }
    private var backendSymbol: String { if case .running = localBackend.state { return "checkmark.circle.fill" }; return "exclamationmark.triangle" }
    private var backendColor: Color { if case .running = localBackend.state { return .green }; return .orange }
    private func icon(for item: String) -> String { ["Главная":"house", "Дела":"folder", "Календарь":"calendar", "Документы":"doc.text", "Почта":"envelope", "Правовой радар":"scope", "Практика":"briefcase", "Черновики":"square.and.pencil", "Голосовые материалы":"waveform", "Аналитика":"chart.bar", "Библиотека норм":"books.vertical", "Проверка контрагентов":"person.text.rectangle", "Настройки":"gearshape"][item] ?? "circle" }
}

private struct JusticeHeroView: View { var body: some View { VStack(spacing: 8) { ZStack { RoundedRectangle(cornerRadius: 20).fill(LinearGradient(colors: [JafarPalette.elevated, JafarPalette.background], startPoint: .top, endPoint: .bottom)); Image(systemName: "scalemass.fill").font(.system(size: 72)).foregroundStyle(JafarPalette.gold.opacity(0.8)); Image(systemName: "crown.fill").font(.system(size: 30)).offset(y: -62).foregroundStyle(JafarPalette.mutedGold) }.frame(height: 190); Text("Центр вашей юридической практики").font(.caption).foregroundStyle(JafarPalette.secondary) } } }
private struct JafarCommandBar: View { @Binding var text: String; let voice: VoiceSessionViewModel; let send: () -> Void; var body: some View { HStack(spacing: 10) { TextField("Спросите Джафара…", text: $text).textFieldStyle(.plain).font(.title3); Button { Task { if voice.isListening { await voice.stopAndSend() } else { await voice.start() } } } label: { Image(systemName: voice.isListening ? "stop.circle.fill" : "mic.fill") }.buttonStyle(.plain).foregroundStyle(JafarPalette.gold); Button(action: send) { Image(systemName: "arrow.up.circle.fill").font(.title2) }.buttonStyle(.plain).foregroundStyle(JafarPalette.gold) }.padding(16).background(JafarPalette.panel, in: Capsule()).overlay(Capsule().stroke(JafarPalette.gold.opacity(0.5))) } }
private struct FocusDayView: View { var body: some View { DashboardCard(title: "Фокус дня") { ForEach([("Требуют внимания", "Проверьте новые задачи"), ("Новые письма", "Gmail не подключён"), ("Новые документы", "Нет новых документов"), ("Ближайшее заседание", "Данные не загружены")], id: \.0) { item in HStack { Image(systemName: "circle").foregroundStyle(JafarPalette.gold); VStack(alignment: .leading) { Text(item.0).foregroundStyle(JafarPalette.text); Text(item.1).font(.caption).foregroundStyle(JafarPalette.secondary) }; Spacer() } } } } }
private struct MattersOverviewView: View { var body: some View { DashboardCard(title: "Мои дела") { Text("Дела пока не загружены").foregroundStyle(JafarPalette.secondary); Button("＋ Новое дело") {}.buttonStyle(.bordered).tint(JafarPalette.gold) } } }
private struct TasksDeadlinesView: View { var body: some View { DashboardCard(title: "Задачи и сроки") { Text("Сроки появятся после подключения данных дел.").font(.caption).foregroundStyle(JafarPalette.secondary) } } }
private struct UpcomingHearingsView: View { var body: some View { DashboardCard(title: "Ближайшие заседания") { Text("Заседания не загружены.").font(.caption).foregroundStyle(JafarPalette.secondary) } } }
private struct JafarActivityView: View { var body: some View { DashboardCard(title: "Активность Джафара") { Text("Локальная активность появится после выполнения команд.").font(.caption).foregroundStyle(JafarPalette.secondary) } } }
private struct LegalRadarView: View { var body: some View { DashboardCard(title: "Правовой радар") { Text("Правовой радар будет подключён к базе актуальной практики.").font(.caption).foregroundStyle(JafarPalette.secondary) } } }
private struct AIAnalyticsView: View { var body: some View { DashboardCard(title: "AI-аналитика") { Text("Метрики будут показаны только на основе подтверждённого анализа.").font(.caption).foregroundStyle(JafarPalette.secondary) } } }
private struct VoiceMaterialsSummaryView: View { var body: some View { DashboardCard(title: "Голосовые материалы") { Text("Записей пока нет.").font(.caption).foregroundStyle(JafarPalette.secondary) } } }

#Preview { ContentView().environmentObject(LocalBackendManager()) }
