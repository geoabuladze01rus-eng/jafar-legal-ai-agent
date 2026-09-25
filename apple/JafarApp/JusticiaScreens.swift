import SwiftUI

struct JusticiaSettingsView: View {
    @AppStorage("justicia.notifications") private var notifications = true
    @AppStorage("justicia.compactSidebar") private var compactSidebar = false
    @AppStorage("justicia.reduceMotion") private var reduceMotion = false

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
                        Circle()
                            .fill(JusticiaTheme.blueSoft)
                            .frame(width: 64, height: 64)
                            .overlay(
                                Image(systemName: "person.fill")
                                    .font(.title)
                                    .foregroundStyle(JusticiaTheme.blue)
                            )

                        VStack(alignment: .leading, spacing: 4) {
                            Text("Профиль юриста")
                                .font(.title3.bold())
                            Text("Локальное рабочее пространство")
                                .font(.caption)
                                .foregroundStyle(JusticiaTheme.secondaryInk)
                        }
                    }

                    Divider()

                    Label(
                        "Данные приложения хранятся локально и шифруются.",
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
                Text("Безопасность")
                    .font(.headline)

                settingsRow("Локальное шифрование", "Включено", "lock.fill", JusticiaTheme.green)
                settingsRow("Облачная отправка конфиденциальных данных", "Выключена", "icloud.slash", JusticiaTheme.green)
                settingsRow("Защищённый локальный API", "Включён", "network.badge.shield.half.filled", JusticiaTheme.green)
            }
            .justiciaCard()
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
