import SwiftUI

enum JusticiaTheme {
    static let canvas = Color(red: 0.965, green: 0.953, blue: 0.929)
    static let surface = Color(red: 0.996, green: 0.988, blue: 0.969)
    static let surfaceMuted = Color(red: 0.939, green: 0.924, blue: 0.892)
    static let sidebar = Color(red: 0.090, green: 0.129, blue: 0.180)
    static let sidebarInk = Color(red: 0.965, green: 0.945, blue: 0.901)
    static let sidebarMuted = sidebarInk.opacity(0.72)
    static let border = Color(red: 0.852, green: 0.830, blue: 0.786)
    static let ink = Color(red: 0.110, green: 0.157, blue: 0.220)
    static let secondaryInk = Color(red: 0.330, green: 0.365, blue: 0.407)
    static let blue = Color(red: 0.190, green: 0.290, blue: 0.400)
    static let blueSoft = Color(red: 0.899, green: 0.919, blue: 0.930)
    static let gold = Color(red: 0.505, green: 0.350, blue: 0.165)
    static let brass = Color(red: 0.864, green: 0.739, blue: 0.520)
    static let green = Color(red: 0.08, green: 0.60, blue: 0.43)
    static let orange = Color(red: 0.94, green: 0.55, blue: 0.08)
    static let red = Color(red: 0.94, green: 0.27, blue: 0.29)
    static let violet = Color(red: 0.46, green: 0.36, blue: 0.89)

    static let corner: CGFloat = 12
    static let largeCorner: CGFloat = 18
    static let sidebarWidth: CGFloat = 228
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
