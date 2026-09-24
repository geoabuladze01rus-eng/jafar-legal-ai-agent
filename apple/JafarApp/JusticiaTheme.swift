import SwiftUI

enum JusticiaTheme {
    static let canvas = Color(red: 0.976, green: 0.973, blue: 0.958)
    static let surface = Color.white
    static let surfaceMuted = Color(red: 0.956, green: 0.966, blue: 0.982)
    static let sidebar = Color(red: 0.972, green: 0.968, blue: 0.951)
    static let border = Color(red: 0.886, green: 0.902, blue: 0.925)
    static let ink = Color(red: 0.075, green: 0.125, blue: 0.235)
    static let secondaryInk = Color(red: 0.37, green: 0.43, blue: 0.53)
    static let blue = Color(red: 0.15, green: 0.39, blue: 0.86)
    static let blueSoft = Color(red: 0.90, green: 0.94, blue: 1.00)
    static let gold = Color(red: 0.73, green: 0.52, blue: 0.22)
    static let green = Color(red: 0.08, green: 0.60, blue: 0.43)
    static let orange = Color(red: 0.94, green: 0.55, blue: 0.08)
    static let red = Color(red: 0.94, green: 0.27, blue: 0.29)
    static let violet = Color(red: 0.46, green: 0.36, blue: 0.89)

    static let corner: CGFloat = 14
    static let largeCorner: CGFloat = 20
    static let sidebarWidth: CGFloat = 226
}

struct JusticiaCardModifier: ViewModifier {
    var padding: CGFloat = 16

    func body(content: Content) -> some View {
        content
            .padding(padding)
            .background(JusticiaTheme.surface)
            .clipShape(RoundedRectangle(cornerRadius: JusticiaTheme.corner, style: .continuous))
            .overlay(
                RoundedRectangle(cornerRadius: JusticiaTheme.corner, style: .continuous)
                    .stroke(JusticiaTheme.border.opacity(0.85), lineWidth: 1)
            )
            .shadow(color: JusticiaTheme.ink.opacity(0.035), radius: 10, x: 0, y: 4)
    }
}

extension View {
    func justiciaCard(padding: CGFloat = 16) -> some View {
        modifier(JusticiaCardModifier(padding: padding))
    }
}

struct JusticiaPill: View {
    let text: String
    let color: Color

    var body: some View {
        Text(text)
            .font(.caption.weight(.semibold))
            .foregroundStyle(color)
            .padding(.horizontal, 9)
            .padding(.vertical, 5)
            .background(color.opacity(0.10))
            .clipShape(Capsule())
    }
}

struct JusticiaIconTile: View {
    let systemName: String
    var color: Color = JusticiaTheme.blue
    var size: CGFloat = 36

    var body: some View {
        Image(systemName: systemName)
            .font(.system(size: size * 0.42, weight: .semibold))
            .foregroundStyle(color)
            .frame(width: size, height: size)
            .background(color.opacity(0.10))
            .clipShape(RoundedRectangle(cornerRadius: size * 0.28, style: .continuous))
    }
}
