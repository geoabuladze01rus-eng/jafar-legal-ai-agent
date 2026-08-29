import SwiftUI

enum JafarPalette {
    static let background = Color(red: 0.035, green: 0.045, blue: 0.055)
    static let elevated = Color(red: 0.065, green: 0.080, blue: 0.095)
    static let card = Color(red: 0.085, green: 0.100, blue: 0.115)
    static let accent = Color(red: 0.78, green: 0.64, blue: 0.30)
    static let accentSoft = accent.opacity(0.18)
    static let success = Color(red: 0.30, green: 0.78, blue: 0.55)
    static let warning = Color(red: 0.95, green: 0.63, blue: 0.25)
    static let danger = Color(red: 0.95, green: 0.36, blue: 0.35)
    static let secondaryText = Color.white.opacity(0.62)

    // Semantic tokens used by the product surface. Keep feature views independent from
    // literal RGB values so the visual language can evolve without touching every screen.
    static let backgroundPrimary = background
    static let backgroundSecondary = elevated
    static let surface = card
    static let surfaceElevated = Color(red: 0.11, green: 0.13, blue: 0.15)
    static let divider = Color.white.opacity(0.10)
    static let textPrimary = Color.white.opacity(0.94)
    static let textSecondary = secondaryText
    static let textMuted = Color.white.opacity(0.42)
    static let accentGold = accent
    static let accentBlue = Color(red: 0.30, green: 0.58, blue: 0.92)
    static let info = accentBlue
}

enum JusticeTypography {
    static let display = Font.system(.largeTitle, design: .serif).weight(.bold)
    static let titleLarge = Font.system(.title, design: .serif).weight(.bold)
    static let title = Font.system(.title3, design: .rounded).weight(.bold)
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
    static let card: CGFloat = 18
    static let large: CGFloat = 28
}

struct JafarCardModifier: ViewModifier {
    func body(content: Content) -> some View {
        content
            .padding(18)
            .background(
                RoundedRectangle(cornerRadius: 22, style: .continuous)
                    .fill(JafarPalette.card)
                    .overlay(
                        RoundedRectangle(cornerRadius: 22, style: .continuous)
                            .stroke(Color.white.opacity(0.08), lineWidth: 1)
                    )
            )
    }
}

extension View {
    func jafarCard() -> some View {
        modifier(JafarCardModifier())
    }
}
