import SwiftUI

struct JafarDashboardView: View {
    @Binding var commandText: String
    @ObservedObject var voice: VoiceSessionViewModel
    let send: () -> Void
    @StateObject private var mattersModel = JafarMattersViewModel()
    var body: some View {
        ScrollView { VStack(alignment: .leading, spacing: 22) {
            HStack { VStack(alignment: .leading) { Text("Доброе утро").font(.largeTitle.weight(.bold)).foregroundStyle(JafarPalette.text); Text("JAFAR AI готов служить вашей практике").foregroundStyle(JafarPalette.secondary) }; Spacer(); Menu("＋ Создать") { Button("Новое дело") {}.disabled(true); Button("Загрузить документ") {}.disabled(true); Button("Новая задача") {}.disabled(true); Text("Действия появятся после подключения данных") }.buttonStyle(.bordered).tint(JafarPalette.gold) }
            Text("Поиск по делам, документам, правовым позициям…").foregroundStyle(JafarPalette.secondary).padding(10).frame(maxWidth: .infinity, alignment: .leading).background(JafarPalette.panel, in: RoundedRectangle(cornerRadius: 8))
            JusticeHeroView(); JafarCommandBar(text: $commandText, voice: voice, send: send); JafarCommandResultView(voice: voice)
            HStack(alignment: .top, spacing: 16) { VStack(spacing: 16) { FocusDayView(); MattersOverviewView(state: mattersModel.state); JafarActivityView() }.frame(maxWidth: .infinity); VStack(spacing: 16) { TasksDeadlinesView(); UpcomingHearingsView(); LegalRadarView(); AIAnalyticsView(); VoiceMaterialsSummaryView() }.frame(width: 300) }
        }.padding(28).frame(maxWidth: 1200, alignment: .leading) }.background(JafarPalette.background)
        .task { mattersModel.load() }
    }
}
private struct JusticeHeroView: View { var body: some View { VStack(spacing: 8) { ZStack { RoundedRectangle(cornerRadius: 20).fill(LinearGradient(colors: [JafarPalette.elevated, JafarPalette.background], startPoint: .top, endPoint: .bottom)); Image(systemName: "scalemass.fill").font(.system(size: 72)).foregroundStyle(JafarPalette.gold.opacity(0.8)); Image(systemName: "crown.fill").font(.system(size: 30)).offset(y: -62).foregroundStyle(JafarPalette.mutedGold) }.frame(height: 190); Text("Центр вашей юридической практики").font(.caption).foregroundStyle(JafarPalette.secondary) } } }
private struct JafarCommandBar: View { @Binding var text: String; @ObservedObject var voice: VoiceSessionViewModel; let send: () -> Void; var body: some View { HStack { TextField("Спросите Джафара…", text: $text).textFieldStyle(.plain).onSubmit(send); Button { Task { if voice.isListening { await voice.stopAndSend() } else { await voice.start() } } } label: { Image(systemName: voice.isListening ? "stop.circle.fill" : "mic.fill") }.accessibilityLabel("Голосовая команда"); Button(action: send) { Image(systemName: "arrow.up.circle.fill") }.accessibilityLabel("Отправить команду") }.padding(16).background(JafarPalette.panel, in: Capsule()).foregroundStyle(JafarPalette.gold) } }
private struct FocusDayView: View { var body: some View { JafarCard(title: "Фокус дня") { Text("Новые письма: данные не загружены").foregroundStyle(JafarPalette.secondary); Text("Ближайшие задачи появятся после подключения данных дел.").font(.caption).foregroundStyle(JafarPalette.secondary) } } }
private struct MattersOverviewView: View { let state: JafarMattersViewModel.State; var body: some View { JafarCard(title: "Мои дела") { switch state { case .idle, .loading: ProgressView(); case let .loaded(items): Text("Дел: \(items.count)").foregroundStyle(JafarPalette.text); case .empty: Text("Дел пока нет").foregroundStyle(JafarPalette.secondary); case let .failed(message): Text(message).foregroundStyle(JafarPalette.secondary) } } } }
private struct TasksDeadlinesView: View { var body: some View { JafarCard(title: "Задачи и сроки") { Text("Сроки появятся после подключения данных дел.").font(.caption).foregroundStyle(JafarPalette.secondary) } } }
private struct UpcomingHearingsView: View { var body: some View { JafarCard(title: "Ближайшие заседания") { Text("Заседания не загружены.").font(.caption).foregroundStyle(JafarPalette.secondary) } } }
private struct JafarActivityView: View { var body: some View { JafarCard(title: "Активность Джафара") { Text("Локальная активность появится после выполнения команд.").font(.caption).foregroundStyle(JafarPalette.secondary) } } }
private struct LegalRadarView: View { var body: some View { JafarCard(title: "Правовой радар") { Text("Правовой радар будет подключён к базе актуальной практики.").font(.caption).foregroundStyle(JafarPalette.secondary) } } }
private struct AIAnalyticsView: View { var body: some View { JafarCard(title: "AI-аналитика") { Text("Метрики будут показаны только на основе подтверждённого анализа.").font(.caption).foregroundStyle(JafarPalette.secondary) } } }
private struct VoiceMaterialsSummaryView: View { var body: some View { JafarCard(title: "Голосовые материалы") { Text("Записей пока нет.").font(.caption).foregroundStyle(JafarPalette.secondary) } } }
