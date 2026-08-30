import SwiftUI

enum JafarPalette {
    static let background = Color(red: 5 / 255, green: 9 / 255, blue: 16 / 255)
    static let elevated = Color(red: 8 / 255, green: 16 / 255, blue: 27 / 255)
    static let card = Color(red: 14 / 255, green: 21 / 255, blue: 31 / 255)
    static let accent = Color(red: 200 / 255, green: 155 / 255, blue: 82 / 255)
    static let accentSoft = accent.opacity(0.18)
    static let success = Color(red: 0.36, green: 0.56, blue: 0.43)
    static let warning = Color(red: 0.78, green: 0.58, blue: 0.25)
    static let danger = Color(red: 0.58, green: 0.22, blue: 0.22)
    static let secondaryText = Color(red: 174 / 255, green: 180 / 255, blue: 190 / 255)

    // Semantic tokens used by the product surface. Keep feature views independent from
    // literal RGB values so the visual language can evolve without touching every screen.
    static let backgroundPrimary = background
    static let backgroundSecondary = elevated
    static let surface = card
    static let surfaceElevated = Color(red: 21 / 255, green: 30 / 255, blue: 41 / 255)
    static let divider = accent.opacity(0.20)
    static let textPrimary = Color(red: 243 / 255, green: 239 / 255, blue: 231 / 255)
    static let textSecondary = secondaryText
    static let textMuted = Color.white.opacity(0.42)
    static let accentGold = accent
    static let accentBlue = Color(red: 0.32, green: 0.48, blue: 0.64)
    static let info = accentBlue
}

enum JusticeTypography {
    static let display = Font.system(.largeTitle, design: .serif).weight(.bold)
    static let titleLarge = Font.system(.title, design: .serif).weight(.bold)
    static let title = Font.system(.title3, design: .serif).weight(.bold)
    static let headline = Font.system(.headline, design: .rounded).weight(.semibold)
    static let body = Font.system(.body, design: .rounded)
    static let callout = Font.system(.callout, design: .rounded)
    static let caption = Font.system(.caption, design: .rounded)
    static let mono = Font.system(.caption, design: .monospaced)
}

enum JusticeSpacing {
    static let xs: CGFloat = 4
    static let sm: CGFloat = 8
    static let md: CGFloat = 14
    static let lg: CGFloat = 20
    static let xl: CGFloat = 28
    static let xxl: CGFloat = 40
}

enum JusticeRadius {
    static let small: CGFloat = 10
    static let card: CGFloat = 8
    static let large: CGFloat = 10
}

struct JafarCardModifier: ViewModifier {
    func body(content: Content) -> some View {
        content
            .padding(16)
            .background(
                RoundedRectangle(cornerRadius: 8, style: .continuous)
                    .fill(JafarPalette.card)
                    .overlay(
                        RoundedRectangle(cornerRadius: 22, style: .continuous)
                            .stroke(JafarPalette.accent.opacity(0.20), lineWidth: 1)
                    )
            )
    }
}

extension View {
    func jafarCard() -> some View {
        modifier(JafarCardModifier())
    }
}
