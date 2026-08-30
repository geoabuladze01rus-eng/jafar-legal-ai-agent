import SwiftUI

struct JusticeOnboardingView: View {
    @AppStorage("justice.onboarding_completed") private var completed = false
    @State private var step = 0
    private let pages = [
        ("ЮСТИЦИЯ AI", "Интеллектуальная система адвоката", "scalemass.fill"),
        ("Работа с делами", "Документы, доказательства, сроки и практика — в одном месте.", "briefcase.fill"),
        ("Совет моделей", "Несколько моделей анализируют задачу независимо и показывают разногласия.", "person.3.fill"),
        ("Контроль адвоката", "Юстиция готовит варианты. Итоговую позицию определяете вы.", "hand.raised.fill"),
        ("Настройте доступ", "Микрофон, речь и Face ID запрашиваются только в контексте соответствующей функции.", "faceid")
    ]

    var body: some View {
        ZStack {
            JafarPalette.backgroundPrimary.ignoresSafeArea()
            VStack(spacing: JusticeSpacing.xl) {
                Spacer()
                Image(systemName: pages[step].2).font(.system(size: 58, weight: .light)).foregroundStyle(JafarPalette.accentGold)
                Text(pages[step].0).font(JusticeTypography.display).multilineTextAlignment(.center)
                Text(pages[step].1).font(JusticeTypography.body).foregroundStyle(JafarPalette.textSecondary).multilineTextAlignment(.center).frame(maxWidth: 440)
                Spacer()
                HStack(spacing: JusticeSpacing.sm) { ForEach(0..<pages.count, id: \.self) { index in Capsule().fill(index == step ? JafarPalette.accentGold : JafarPalette.textMuted).frame(width: index == step ? 24 : 8, height: 6) } }
                Button(step == pages.count - 1 ? "Начать работу" : "Продолжить") { if step == pages.count - 1 { completed = true } else { step += 1 } }.buttonStyle(.borderedProminent).tint(JafarPalette.accentGold).controlSize(.large)
                Button("Пропустить") { completed = true }.font(JusticeTypography.caption).foregroundStyle(JafarPalette.textSecondary)
            }.padding(JusticeSpacing.xl).frame(maxWidth: 620)
        }.preferredColorScheme(.dark)
    }
}
