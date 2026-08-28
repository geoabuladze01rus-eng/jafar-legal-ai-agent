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
