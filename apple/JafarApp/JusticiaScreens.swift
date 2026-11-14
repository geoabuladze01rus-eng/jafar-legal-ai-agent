import SwiftUI

struct JusticiaSettingsView: View {
    @Binding var avatarData: Data
    @AppStorage("justicia.notifications") private var notifications = true
    @AppStorage("justicia.compactSidebar") private var compactSidebar = false
    @AppStorage("justicia.reduceMotion") private var reduceMotion = false
    @AppStorage("justicia.onboardingCompleted") private var onboardingCompleted = false
    @State private var choosingAvatar = false
    @State private var importingAvatar = false
    @State private var avatarError: String?

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            pageHeader(
                title: "Настройки",
                subtitle: "Комфорт длительной работы, локальный ИИ и параметры защищённого рабочего пространства."
            )

            HStack(alignment: .top, spacing: 14) {
                VStack(alignment: .leading, spacing: 16) {
                    Text("Профиль")
                        .font(.headline)

                    HStack(spacing: 14) {
                        JusticiaAvatar(data: avatarData, size: 64)
                        VStack(alignment: .leading, spacing: 4) {
                            Text("Профиль юриста")
                                .font(.system(.title3, design: .serif, weight: .semibold))
                            Text("Фото профиля хранится на этом устройстве.")
                                .font(.caption)
                                .foregroundStyle(JusticiaTheme.secondaryInk)
                        }
                    }

                    HStack(spacing: 10) {
                        Button(avatarData.isEmpty ? "Выбрать фото…" : "Сменить фото…") {
                            avatarError = nil
                            choosingAvatar = true
                        }
                        .buttonStyle(.borderedProminent)

                        if !avatarData.isEmpty {
                            Button("Удалить фото") {
                                avatarData = Data()
                                avatarError = nil
                            }
                            .buttonStyle(.bordered)
                        }
                        if importingAvatar {
                            ProgressView()
                                .controlSize(.small)
                                .accessibilityLabel("Загружаем фото")
                        }
                    }
                    .disabled(importingAvatar)

                    if let avatarError {
                        Text(avatarError)
                            .font(.caption)
                            .foregroundStyle(JusticiaTheme.red)
                    }

                    Divider()

                    Label(
                        "Дела и документы хранятся в зашифрованном хранилище.",
                        systemImage: "lock.shield"
                    )
                    .font(.caption)
                    .foregroundStyle(JusticiaTheme.secondaryInk)
                }
                .justiciaCard()
                .frame(maxWidth: .infinity)

                VStack(alignment: .leading, spacing: 14) {
                    Text("Интерфейс")
                        .font(.headline)

                    HStack(spacing: 12) {
                        JusticiaIconTile(systemName: "sun.max.fill", color: JusticiaTheme.gold, size: 34)

                        VStack(alignment: .leading, spacing: 3) {
                            Text("Светлая тема")
                                .font(.subheadline.weight(.semibold))
                            Text("Основная тема «Юстиции» для длительной работы с документами.")
                                .font(.caption)
                                .foregroundStyle(JusticiaTheme.secondaryInk)
                        }

                        Spacer()

                        JusticiaPill(text: "Включена", color: JusticiaTheme.green)
                    }

                    Divider()

                    Toggle("Компактная боковая панель", isOn: $compactSidebar)
                    Toggle("Показывать уведомления", isOn: $notifications)
                    Toggle("Уменьшить анимацию", isOn: $reduceMotion)

                    Text("Эти настройки сохраняются на этом устройстве.")
                        .font(.caption)
                        .foregroundStyle(JusticiaTheme.secondaryInk)
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
                Text("Первый запуск")
                    .font(.headline)
                HStack {
                    VStack(alignment: .leading, spacing: 3) {
                        Text("Ознакомление с «Юстицией»")
                            .font(.subheadline.weight(.semibold))
                        Text("Повторно показать краткое введение по локальным данным, ИИ и транскрибации.")
                            .font(.caption)
                            .foregroundStyle(JusticiaTheme.secondaryInk)
                    }
                    Spacer()
                    Button("Показать снова") {
                        onboardingCompleted = false
                    }
                    .buttonStyle(.bordered)
                }
            }
            .justiciaCard()

            VStack(alignment: .leading, spacing: 12) {
                JusticiaBetaDiagnosticsView()
            }
            .justiciaCard()

            VStack(alignment: .leading, spacing: 12) {
                JusticiaBetaFeedbackView()
            }
            .justiciaCard()

            VStack(alignment: .leading, spacing: 12) {
                Text("Безопасность")
                    .font(.headline)

                settingsRow("Локальное шифрование", "Включено", "lock.fill", JusticiaTheme.green)
                settingsRow("Облачная отправка конфиденциальных данных", "Выключена", "icloud.slash", JusticiaTheme.green)
                settingsRow("Защищённый локальный API", "Включён", "network.badge.shield.half.filled", JusticiaTheme.green)
            }
            .justiciaCard()
        }
        .fileImporter(isPresented: $choosingAvatar, allowedContentTypes: JusticiaAvatarPhoto.allowedTypes) { result in
            Task { @MainActor in
                switch result {
                case .success(let url):
                    importingAvatar = true
                    defer { importingAvatar = false }
                    do {
                        let photo = try await Task.detached(priority: .userInitiated) {
                            try JusticiaAvatarPhoto.importPhoto(from: url)
                        }.value
                        avatarData = photo
                    } catch let error as JusticiaAvatarPhoto.ImportError {
                        avatarError = error.localizedDescription
                    } catch {
                        avatarError = "Не удалось прочитать выбранный файл."
                    }
                case .failure(let error):
                    let failure = error as NSError
                    if failure.domain != NSCocoaErrorDomain || failure.code != NSUserCancelledError {
                        avatarError = "Не удалось открыть выбранный файл."
                    }
                }
            }
        }
    }

    private func settingsRow(_ title: String, _ status: String, _ icon: String, _ color: Color) -> some View {
        HStack {
            JusticiaIconTile(systemName: icon, color: color, size: 32)
            Text(title)
                .font(.subheadline)
            Spacer()
            JusticiaPill(text: status, color: color)
        }
    }
}

@ViewBuilder
func pageHeader(title: String, subtitle: String) -> some View {
    VStack(alignment: .leading, spacing: 5) {
        Text(title)
            .font(.system(size: 30, weight: .semibold, design: .serif))
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
