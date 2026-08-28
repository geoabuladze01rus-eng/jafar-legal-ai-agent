import SwiftUI

struct ContentView: View {
    @StateObject private var voice = VoiceSessionViewModel(
        commandClient: LocalCommandClient(),
        userId: "local-user"
    )
    @StateObject private var alerts = JafarAlertsStore()

    private let columns = [
        GridItem(.adaptive(minimum: 165), spacing: 12)
    ]

    var body: some View {
        NavigationStack {
            ZStack {
                JafarPalette.background
                    .ignoresSafeArea()

                ScrollView {
                    VStack(alignment: .leading, spacing: 22) {
                        header
                        trustStrip
                        voiceConsole
                        conversation
                        alertCenter
                        modules
                        reviewGate
                    }
                    .frame(maxWidth: 900)
                    .padding(.horizontal, 18)
                    .padding(.top, 16)
                    .padding(.bottom, 36)
                    .frame(maxWidth: .infinity)
                }
            }
            .navigationDestination(for: JafarModule.self) { module in
                JafarModuleDetailView(module: module)
            }
            .toolbar {
                ToolbarItem(placement: .primaryAction) {
                    Button {
                        // Settings are intentionally a separate future workflow.
                    } label: {
                        Image(systemName: "slider.horizontal.3")
                    }
                    .accessibilityLabel("Настройки")
                }
            }
        }
        .preferredColorScheme(.dark)
    }

    private var header: some View {
        HStack(alignment: .center, spacing: 14) {
            ZStack {
                RoundedRectangle(cornerRadius: 16, style: .continuous)
                    .fill(JafarPalette.accentSoft)
                    .frame(width: 52, height: 52)
                Image(systemName: "shield.lefthalf.filled")
                    .font(.title2.weight(.semibold))
                    .foregroundStyle(JafarPalette.accent)
            }

            VStack(alignment: .leading, spacing: 3) {
                Text("ДЖАФАР")
                    .font(.title2.weight(.heavy))
                    .tracking(1.4)
                Text("ИИ-помощник адвоката")
                    .font(.subheadline)
                    .foregroundStyle(JafarPalette.secondaryText)
            }

            Spacer()

            Text("АДВОКАТСКИЙ РЕЖИМ")
                .font(.caption2.weight(.bold))
                .foregroundStyle(JafarPalette.accent)
                .padding(.horizontal, 10)
                .padding(.vertical, 7)
                .background(Capsule().fill(JafarPalette.accentSoft))
        }
    }

    private var trustStrip: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 9) {
                statusChip(
                    "Конфиденциальность",
                    icon: "lock.shield.fill",
                    color: JafarPalette.success
                )
                statusChip(
                    "Human approval",
                    icon: "person.badge.shield.checkmark.fill",
                    color: JafarPalette.accent
                )
                statusChip(
                    "Audit trail",
                    icon: "clock.arrow.circlepath",
                    color: JafarPalette.secondaryText
                )
            }
        }
    }

    private var voiceConsole: some View {
        VStack(spacing: 18) {
            HStack {
                VStack(alignment: .leading, spacing: 5) {
                    Text("Голосовой помощник")
                        .font(.headline)
                    Text(voiceStatus)
                        .font(.subheadline)
                        .foregroundStyle(JafarPalette.secondaryText)
                }
                Spacer()
                Image(systemName: voice.isListening ? "waveform" : "sparkles")
                    .font(.title2)
                    .foregroundStyle(
                        voice.isListening ? JafarPalette.danger : JafarPalette.accent
                    )
            }

            Button {
                Task {
                    if voice.isListening {
                        await voice.stopAndSend()
                    } else {
                        await voice.start()
                    }
                }
            } label: {
                ZStack {
                    Circle()
                        .fill(
                            (voice.isListening ? JafarPalette.danger : JafarPalette.accent)
                                .opacity(0.16)
                        )
                        .frame(width: 112, height: 112)
                    Circle()
                        .fill(voice.isListening ? JafarPalette.danger : JafarPalette.accent)
                        .frame(width: 78, height: 78)
                        .shadow(
                            color: (
                                voice.isListening ? JafarPalette.danger : JafarPalette.accent
                            ).opacity(0.30),
                            radius: 18
                        )
                    Image(systemName: voice.isListening ? "stop.fill" : "mic.fill")
                        .font(.system(size: 28, weight: .bold))
                        .foregroundStyle(JafarPalette.background)
                }
            }
            .buttonStyle(.plain)
            .accessibilityLabel(
                voice.isListening ? "Остановить и отправить" : "Начать голосовую команду"
            )

            Text(
                voice.isListening
                    ? "Нажмите, чтобы завершить и отправить"
                    : "Нажмите и говорите естественно"
            )
            .font(.caption)
            .foregroundStyle(JafarPalette.secondaryText)
        }
        .frame(maxWidth: .infinity)
        .jafarCard()
    }

    @ViewBuilder
    private var conversation: some View {
        if !voice.transcript.isEmpty || !voice.response.isEmpty || voice.errorMessage != nil {
            VStack(alignment: .leading, spacing: 12) {
                if !voice.transcript.isEmpty {
                    messageBlock(
                        title: "Вы",
                        text: voice.transcript,
                        icon: "person.fill",
                        color: JafarPalette.secondaryText
                    )
                }
                if !voice.response.isEmpty {
                    messageBlock(
                        title: "Джафар",
                        text: voice.response,
                        icon: "shield.fill",
                        color: JafarPalette.accent
                    )
                }
                if let error = voice.errorMessage {
                    messageBlock(
                        title: "Нужна проверка",
                        text: error,
                        icon: "exclamationmark.triangle.fill",
                        color: JafarPalette.danger
                    )
                }
            }
        }
    }

    private var alertCenter: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .firstTextBaseline) {
                sectionTitle(
                    "Сигналы и одобрения",
                    subtitle: "Срочные изменения, риски и действия, требующие решения"
                )
                Spacer()
                if !alerts.alerts.isEmpty {
                    Text("\(alerts.alerts.count)")
                        .font(.caption.weight(.bold))
                        .foregroundStyle(JafarPalette.background)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 4)
                        .background(Capsule().fill(JafarPalette.accent))
                }
            }

            if alerts.alerts.isEmpty {
                HStack(spacing: 12) {
                    Image(systemName: "checkmark.shield.fill")
                        .font(.title3)
                        .foregroundStyle(JafarPalette.success)
                    VStack(alignment: .leading, spacing: 3) {
                        Text("Нет срочных сигналов")
                            .font(.subheadline.weight(.semibold))
                        Text("Здесь появятся новые сроки, изменения практики и правки на одобрение.")
                            .font(.caption)
                            .foregroundStyle(JafarPalette.secondaryText)
                    }
                    Spacer(minLength: 0)
                }
                .jafarCard()
            } else {
                VStack(spacing: 10) {
                    ForEach(Array(alerts.alerts.prefix(3))) { alert in
                        alertRow(alert)
                    }
                }
            }
        }
    }

    private var modules: some View {
        VStack(alignment: .leading, spacing: 12) {
            sectionTitle(
                "Рабочее пространство",
                subtitle: "Ключевые модули юридической практики"
            )
            LazyVGrid(columns: columns, spacing: 12) {
                ForEach(JafarModule.allCases) { module in
                    NavigationLink(value: module) {
                        moduleCard(module)
                    }
                    .buttonStyle(.plain)
                }
            }
        }
    }

    private var reviewGate: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack {
                Image(systemName: "checkmark.seal.fill")
                    .foregroundStyle(JafarPalette.success)
                Text("Контроль юридических правок")
                    .font(.headline)
                Spacer()
                Text("ВКЛЮЧЁН")
                    .font(.caption2.weight(.bold))
                    .foregroundStyle(JafarPalette.success)
            }

            gateRow(
                "Новая практика не меняет документ автоматически",
                icon: "hand.raised.fill"
            )
            gateRow(
                "Каждая правка привязана к authority и source refs",
                icon: "link"
            )
            gateRow(
                "Применение и rollback фиксируются в audit ledger",
                icon: "arrow.uturn.backward.circle.fill"
            )
        }
        .jafarCard()
    }

    private var voiceStatus: String {
        if voice.isListening { return "Слушаю команду…" }
        if voice.isSpeaking { return "Отвечаю голосом…" }
        return "Готов к команде"
    }

    private func statusChip(_ title: String, icon: String, color: Color) -> some View {
        Label(title, systemImage: icon)
            .font(.caption.weight(.semibold))
            .foregroundStyle(color)
            .padding(.horizontal, 11)
            .padding(.vertical, 8)
            .background(Capsule().fill(JafarPalette.elevated))
            .overlay(Capsule().stroke(Color.white.opacity(0.06), lineWidth: 1))
    }

    private func messageBlock(title: String, text: String, icon: String, color: Color) -> some View {
        HStack(alignment: .top, spacing: 12) {
            Image(systemName: icon)
                .foregroundStyle(color)
                .frame(width: 24)
            VStack(alignment: .leading, spacing: 5) {
                Text(title)
                    .font(.caption.weight(.bold))
                    .foregroundStyle(color)
                Text(text)
                    .font(.body)
                    .foregroundStyle(.white.opacity(0.92))
                    .textSelection(.enabled)
            }
            Spacer(minLength: 0)
        }
        .jafarCard()
    }

    private func alertRow(_ alert: JafarAlert) -> some View {
        HStack(alignment: .top, spacing: 12) {
            Image(systemName: alert.requiresApproval ? "checkmark.seal.fill" : "bell.badge.fill")
                .foregroundStyle(alertColor(alert.priority))
                .frame(width: 24)

            VStack(alignment: .leading, spacing: 5) {
                HStack(spacing: 8) {
                    Text(alert.title)
                        .font(.subheadline.weight(.semibold))
                    if alert.requiresApproval {
                        Text("ОДОБРЕНИЕ")
                            .font(.caption2.weight(.bold))
                            .foregroundStyle(JafarPalette.accent)
                    }
                }
                Text(alert.body)
                    .font(.caption)
                    .foregroundStyle(JafarPalette.secondaryText)
                    .lineLimit(3)
            }

            Spacer(minLength: 0)

            Button {
                alerts.dismiss(alert.id)
            } label: {
                Image(systemName: "xmark")
                    .font(.caption.weight(.bold))
                    .foregroundStyle(JafarPalette.secondaryText)
            }
            .buttonStyle(.plain)
            .accessibilityLabel("Скрыть сигнал")
        }
        .jafarCard()
    }

    private func alertColor(_ priority: Int) -> Color {
        if priority >= 80 { return JafarPalette.danger }
        if priority >= 50 { return JafarPalette.warning }
        return JafarPalette.accent
    }

    private func sectionTitle(_ title: String, subtitle: String) -> some View {
        VStack(alignment: .leading, spacing: 3) {
            Text(title)
                .font(.title3.weight(.bold))
            Text(subtitle)
                .font(.subheadline)
                .foregroundStyle(JafarPalette.secondaryText)
        }
    }

    private func moduleCard(_ module: JafarModule) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: module.icon)
                    .font(.title3.weight(.semibold))
                    .foregroundStyle(JafarPalette.accent)
                Spacer()
                Image(systemName: "chevron.right")
                    .font(.caption.weight(.bold))
                    .foregroundStyle(JafarPalette.secondaryText)
            }
            Text(module.title)
                .font(.headline)
                .foregroundStyle(.white)
            Text(module.subtitle)
                .font(.caption)
                .foregroundStyle(JafarPalette.secondaryText)
                .multilineTextAlignment(.leading)
                .lineLimit(2)
        }
        .frame(maxWidth: .infinity, minHeight: 118, alignment: .topLeading)
        .jafarCard()
    }

    private func gateRow(_ text: String, icon: String) -> some View {
        HStack(alignment: .top, spacing: 10) {
            Image(systemName: icon)
                .foregroundStyle(JafarPalette.accent)
                .frame(width: 20)
            Text(text)
                .font(.subheadline)
                .foregroundStyle(.white.opacity(0.82))
            Spacer(minLength: 0)
        }
    }
}

private struct JafarModuleDetailView: View {
    let module: JafarModule

    var body: some View {
        ZStack {
            JafarPalette.background
                .ignoresSafeArea()
            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    HStack(spacing: 14) {
                        Image(systemName: module.icon)
                            .font(.title2)
                            .foregroundStyle(JafarPalette.accent)
                            .frame(width: 48, height: 48)
                            .background(
                                RoundedRectangle(cornerRadius: 14)
                                    .fill(JafarPalette.accentSoft)
                            )
                        VStack(alignment: .leading, spacing: 3) {
                            Text(module.title)
                                .font(.title2.weight(.bold))
                            Text(module.subtitle)
                                .foregroundStyle(JafarPalette.secondaryText)
                        }
                    }

                    VStack(alignment: .leading, spacing: 12) {
                        ForEach(module.detailPoints, id: \.self) { point in
                            HStack(alignment: .top, spacing: 10) {
                                Image(systemName: "checkmark.circle.fill")
                                    .foregroundStyle(JafarPalette.success)
                                Text(point)
                                    .foregroundStyle(.white.opacity(0.88))
                                Spacer(minLength: 0)
                            }
                        }
                    }
                    .jafarCard()

                    HStack(alignment: .top, spacing: 10) {
                        Image(systemName: "lock.shield.fill")
                            .foregroundStyle(JafarPalette.accent)
                        Text(
                            "Юридически значимые действия, отправка документов и изменение "
                                + "рабочей позиции требуют отдельного подтверждения адвоката."
                        )
                        .font(.footnote)
                        .foregroundStyle(JafarPalette.secondaryText)
                    }
                    .jafarCard()
                }
                .frame(maxWidth: 760)
                .padding(18)
                .frame(maxWidth: .infinity)
            }
        }
        .navigationTitle(module.title)
        .preferredColorScheme(.dark)
    }
}

#Preview {
    ContentView()
}
