import SwiftUI

struct JusticiaOnboardingView: View {
    @AppStorage("justicia.onboardingCompleted") private var onboardingCompleted = false
    @State private var step = 0

    private let steps = 4

    var body: some View {
        ZStack {
            JusticiaTheme.canvas.ignoresSafeArea()

            VStack(spacing: 24) {
                header

                Group {
                    switch step {
                    case 0:
                        welcomeStep
                    case 1:
                        privacyStep
                    case 2:
                        localAIStep
                    default:
                        transcriptionStep
                    }
                }
                .frame(maxWidth: 760)

                footer
            }
            .padding(34)
        }
        .frame(minWidth: 860, minHeight: 620)
    }

    private var header: some View {
        HStack {
            HStack(spacing: 11) {
                ZStack {
                    RoundedRectangle(cornerRadius: 12, style: .continuous)
                        .fill(JusticiaTheme.gold.opacity(0.12))
                    Image(systemName: "scalemass")
                        .font(.system(size: 24, weight: .semibold))
                        .foregroundStyle(JusticiaTheme.gold)
                }
                .frame(width: 46, height: 46)

                VStack(alignment: .leading, spacing: 2) {
                    Text("Юстиция")
                        .font(.system(size: 26, weight: .bold, design: .serif))
                        .foregroundStyle(JusticiaTheme.ink)
                    Text("Первый запуск")
                        .font(.caption)
                        .foregroundStyle(JusticiaTheme.secondaryInk)
                }
            }

            Spacer()

            Text("\(step + 1) из \(steps)")
                .font(.caption.weight(.semibold))
                .foregroundStyle(JusticiaTheme.secondaryInk)
        }
    }

    private var welcomeStep: some View {
        VStack(spacing: 22) {
            JusticiaIconTile(systemName: "sparkles", color: JusticiaTheme.blue, size: 64)

            VStack(spacing: 10) {
                Text("Рабочая среда юриста")
                    .font(.system(size: 30, weight: .bold, design: .rounded))
                    .foregroundStyle(JusticiaTheme.ink)

                Text("Дела, документы, сроки, локальный ИИ и транскрибация собраны в одном приложении. «Юстиция» ориентирована на спокойную длительную работу с юридическими материалами.")
                    .font(.body)
                    .foregroundStyle(JusticiaTheme.secondaryInk)
                    .multilineTextAlignment(.center)
                    .lineSpacing(5)
                    .frame(maxWidth: 620)
            }

            HStack(spacing: 14) {
                feature("Дела", "briefcase", "Материалы, участники и сроки")
                feature("Документы", "doc.text", "Локальный корпус и поиск")
                feature("ИИ", "sparkles", "Локальная помощь через Ollama")
            }
        }
    }

    private var privacyStep: some View {
        VStack(alignment: .leading, spacing: 18) {
            pageTitle(
                icon: "lock.shield.fill",
                title: "Конфиденциальность по умолчанию",
                subtitle: "Юридические материалы не должны уходить во внешние сервисы незаметно для пользователя."
            )

            infoRow("Локальное хранение", "Дела и импортированные документы сохраняются в локальном зашифрованном хранилище.", "internaldrive.fill", JusticiaTheme.green)
            infoRow("Без автоматического облака", "Облачная отправка конфиденциальных материалов не включается автоматически.", "icloud.slash", JusticiaTheme.green)
            infoRow("Локальный API", "Desktop-интерфейс работает через защищённый loopback-канал на вашем Mac.", "network.badge.shield.half.filled", JusticiaTheme.blue)
            infoRow("Проверяемость", "Цитаты, provenance и привязка к конкретному делу сохраняются отдельно от выводов ИИ.", "checkmark.shield", JusticiaTheme.violet)
        }
        .justiciaCard(padding: 22)
    }

    private var localAIStep: some View {
        VStack(alignment: .leading, spacing: 18) {
            pageTitle(
                icon: "cpu",
                title: "Локальный ИИ",
                subtitle: "Для конфиденциальной работы «Юстиция» использует локальный Ollama на вашем компьютере."
            )

            #if os(macOS)
            LocalAIStatusView()
            #else
            infoRow("Ollama", "Проверка локального движка доступна в macOS-версии.", "desktopcomputer", JusticiaTheme.blue)
            #endif

            VStack(alignment: .leading, spacing: 9) {
                Text("Что важно понимать")
                    .font(.headline)
                Label("Рекомендуемая локальная модель — qwen3:4b.", systemImage: "checkmark.circle")
                Label("Если локальный ИИ недоступен, «Юстиция» не должна молча переключаться на облачный анализ конфиденциальных материалов.", systemImage: "checkmark.circle")
                Label("Статус Ollama всегда можно проверить в Настройках.", systemImage: "checkmark.circle")
            }
            .font(.subheadline)
            .foregroundStyle(JusticiaTheme.secondaryInk)
        }
        .justiciaCard(padding: 22)
    }

    private var transcriptionStep: some View {
        VStack(alignment: .leading, spacing: 18) {
            pageTitle(
                icon: "waveform",
                title: "Транскрибация × PLAUD",
                subtitle: "Записи можно расшифровывать локально и сохранять прямо в материалы выбранного дела."
            )

            infoRow("On-device распознавание", "И микрофон, и загруженный аудиофайл требуют локального распознавания на устройстве.", "desktopcomputer.and.arrow.down", JusticiaTheme.green)
            infoRow("Сохранение в дело", "Проверенный транскрипт можно сохранить как отдельный документ в локальный зашифрованный корпус.", "folder.badge.plus", JusticiaTheme.blue)
            infoRow("PLAUD", "Сейчас это предлагаемое партнёрство. Официальная интеграция и использование совместного брендинга будут расширены только после согласования с PLAUD.", "waveform.badge.plus", JusticiaTheme.orange)

            Text("Начните с создания дела, загрузите документы и при необходимости добавьте запись или аудиофайл.")
                .font(.subheadline)
                .foregroundStyle(JusticiaTheme.secondaryInk)
        }
        .justiciaCard(padding: 22)
    }

    private var footer: some View {
        HStack {
            Button("Назад") {
                step = max(0, step - 1)
            }
            .buttonStyle(.bordered)
            .disabled(step == 0)

            Spacer()

            HStack(spacing: 6) {
                ForEach(0..<steps, id: \.self) { index in
                    Capsule()
                        .fill(index == step ? JusticiaTheme.blue : JusticiaTheme.border)
                        .frame(width: index == step ? 24 : 8, height: 8)
                }
            }

            Spacer()

            if step < steps - 1 {
                Button("Продолжить") {
                    step += 1
                }
                .buttonStyle(.borderedProminent)
                .keyboardShortcut(.defaultAction)
            } else {
                Button("Начать работу") {
                    onboardingCompleted = true
                }
                .buttonStyle(.borderedProminent)
                .keyboardShortcut(.defaultAction)
            }
        }
    }

    private func pageTitle(icon: String, title: String, subtitle: String) -> some View {
        HStack(alignment: .top, spacing: 14) {
            JusticiaIconTile(systemName: icon, color: JusticiaTheme.blue, size: 48)
            VStack(alignment: .leading, spacing: 5) {
                Text(title)
                    .font(.title2.bold())
                    .foregroundStyle(JusticiaTheme.ink)
                Text(subtitle)
                    .font(.subheadline)
                    .foregroundStyle(JusticiaTheme.secondaryInk)
                    .lineSpacing(4)
            }
            Spacer()
        }
    }

    private func feature(_ title: String, _ icon: String, _ subtitle: String) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            JusticiaIconTile(systemName: icon, color: JusticiaTheme.blue)
            Text(title)
                .font(.headline)
            Text(subtitle)
                .font(.caption)
                .foregroundStyle(JusticiaTheme.secondaryInk)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .justiciaCard()
    }

    private func infoRow(_ title: String, _ text: String, _ icon: String, _ color: Color) -> some View {
        HStack(alignment: .top, spacing: 12) {
            JusticiaIconTile(systemName: icon, color: color, size: 36)
            VStack(alignment: .leading, spacing: 4) {
                Text(title)
                    .font(.subheadline.weight(.semibold))
                Text(text)
                    .font(.caption)
                    .foregroundStyle(JusticiaTheme.secondaryInk)
                    .lineSpacing(3)
            }
            Spacer()
        }
    }
}
