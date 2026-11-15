import SwiftUI

enum JusticiaAvatarHelper {
    static let availableIcons: [(id: String, title: String)] = [
        ("person.fill", "Классический"),
        ("briefcase.fill", "Корпоративный"),
        ("building.columns.fill", "Судебный"),
        ("scale.3d", "Арбитраж"),
        ("scroll.fill", "Договорной"),
        ("shield.lefthalf.filled", "Защита"),
        ("signature", "Нотариат"),
        ("graduationcap.fill", "Экспертиза")
    ]

    static let availableColors: [(id: String, name: String, color: Color, soft: Color)] = [
        ("blue", "Синий", JusticiaTheme.blue, JusticiaTheme.blueSoft),
        ("gold", "Золотой", JusticiaTheme.gold, Color(red: 0.98, green: 0.95, blue: 0.88)),
        ("green", "Изумрудный", JusticiaTheme.green, Color(red: 0.88, green: 0.97, blue: 0.93)),
        ("violet", "Фиолетовый", JusticiaTheme.violet, Color(red: 0.94, green: 0.92, blue: 0.99)),
        ("orange", "Терракотовый", JusticiaTheme.orange, Color(red: 0.99, green: 0.94, blue: 0.88))
    ]

    static func color(for id: String) -> (color: Color, soft: Color) {
        if let match = availableColors.first(where: { $0.id == id }) {
            return (match.color, match.soft)
        }
        return (JusticiaTheme.blue, JusticiaTheme.blueSoft)
    }
}

struct LawyerAvatarView: View {
    let iconName: String
    let colorID: String
    var size: CGFloat = 36
    var iconSize: CGFloat = 18

    var body: some View {
        let palette = JusticiaAvatarHelper.color(for: colorID)
        Circle()
            .fill(palette.soft)
            .frame(width: size, height: size)
            .overlay(
                Image(systemName: iconName)
                    .font(.system(size: iconSize, weight: .semibold))
                    .foregroundStyle(palette.color)
            )
            .overlay(
                Circle()
                    .strokeBorder(palette.color.opacity(0.35), lineWidth: 1.5)
            )
    }
}

struct JusticiaSettingsView: View {
    @AppStorage("justicia.lawyerAvatar") private var lawyerAvatar = "person.fill"
    @AppStorage("justicia.avatarColor") private var avatarColor = "blue"
    @AppStorage("justicia.lawyerName") private var lawyerName = "Юрист"
    @AppStorage("justicia.lawyerRole") private var lawyerRole = "Адвокат / Корпоративный юрист"
    @AppStorage("justicia.notifications") private var notifications = true
    @AppStorage("justicia.compactSidebar") private var compactSidebar = false
    @AppStorage("justicia.reduceMotion") private var reduceMotion = false
    @AppStorage("justicia.onboardingCompleted") private var onboardingCompleted = false

    @State private var showAvatarCustomizer = false

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            pageHeader(
                title: "Настройки",
                subtitle: "Комфорт длительной работы, локальный ИИ и параметры защищённого рабочего пространства."
            )

            HStack(alignment: .top, spacing: 14) {
                VStack(alignment: .leading, spacing: 16) {
                    HStack {
                        Text("Профиль")
                            .font(.headline)
                        Spacer()
                        Button {
                            withAnimation(.easeInOut(duration: 0.2)) {
                                showAvatarCustomizer.toggle()
                            }
                        } label: {
                            Label(showAvatarCustomizer ? "Скрыть" : "Сменить аватар", systemImage: "paintbrush.fill")
                                .font(.caption.weight(.medium))
                        }
                        .buttonStyle(.bordered)
                        .controlSize(.small)
                    }

                    HStack(spacing: 14) {
                        LawyerAvatarView(
                            iconName: lawyerAvatar,
                            colorID: avatarColor,
                            size: 58,
                            iconSize: 26
                        )

                        VStack(alignment: .leading, spacing: 6) {
                            TextField("Имя юриста", text: $lawyerName)
                                .textFieldStyle(.plain)
                                .font(.title3.bold())
                                .foregroundStyle(JusticiaTheme.ink)

                            TextField("Специализация", text: $lawyerRole)
                                .textFieldStyle(.plain)
                                .font(.caption)
                                .foregroundStyle(JusticiaTheme.secondaryInk)
                        }
                    }

                    if showAvatarCustomizer {
                        VStack(alignment: .leading, spacing: 10) {
                            Text("Символ специализации:")
                                .font(.caption.weight(.semibold))
                                .foregroundStyle(JusticiaTheme.secondaryInk)

                            LazyVGrid(columns: Array(repeating: GridItem(.flexible(), spacing: 8), count: 4), spacing: 8) {
                                ForEach(JusticiaAvatarHelper.availableIcons, id: \.id) { item in
                                    Button {
                                        lawyerAvatar = item.id
                                    } label: {
                                        VStack(spacing: 4) {
                                            Image(systemName: item.id)
                                                .font(.system(size: 18, weight: .medium))
                                            Text(item.title)
                                                .font(.system(size: 10))
                                                .lineLimit(1)
                                        }
                                        .frame(maxWidth: .infinity)
                                        .padding(.vertical, 8)
                                        .background(lawyerAvatar == item.id ? JusticiaTheme.blueSoft : JusticiaTheme.surfaceMuted)
                                        .foregroundStyle(lawyerAvatar == item.id ? JusticiaTheme.blue : JusticiaTheme.ink)
                                        .clipShape(RoundedRectangle(cornerRadius: 8))
                                        .overlay(
                                            RoundedRectangle(cornerRadius: 8)
                                                .strokeBorder(lawyerAvatar == item.id ? JusticiaTheme.blue : Color.clear, lineWidth: 1.5)
                                        )
                                    }
                                    .buttonStyle(.plain)
                                }
                            }

                            Text("Цветовой акцент:")
                                .font(.caption.weight(.semibold))
                                .foregroundStyle(JusticiaTheme.secondaryInk)
                                .padding(.top, 4)

                            HStack(spacing: 12) {
                                ForEach(JusticiaAvatarHelper.availableColors, id: \.id) { col in
                                    Button {
                                        avatarColor = col.id
                                    } label: {
                                        Circle()
                                            .fill(col.color)
                                            .frame(width: 24, height: 24)
                                            .overlay(
                                                Circle()
                                                    .strokeBorder(Color.white, lineWidth: 2)
                                            )
                                            .overlay(
                                                Circle()
                                                    .strokeBorder(avatarColor == col.id ? JusticiaTheme.ink : Color.clear, lineWidth: 2)
                                                    .frame(width: 30, height: 30)
                                            )
                                    }
                                    .buttonStyle(.plain)
                                }
                            }
                        }
                        .padding(12)
                        .background(JusticiaTheme.surfaceMuted.opacity(0.6))
                        .clipShape(RoundedRectangle(cornerRadius: 10))
                    }

                    Divider()

                    Label(
                        "Данные профиля и дел хранятся локально и шифруются.",
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
