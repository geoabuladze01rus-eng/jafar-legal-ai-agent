import SwiftUI

enum JusticePresenceState: Equatable, Sendable {
    case calm
    case analyzing
    case control

    var title: String {
        switch self {
        case .calm:
            return "Готова"
        case .analyzing:
            return "Анализирует"
        case .control:
            return "Требуется решение"
        }
    }

    var systemImage: String {
        switch self {
        case .calm, .analyzing:
            return "scalemass.fill"
        case .control:
            return "hand.raised.fill"
        }
    }
}

struct JusticePresenceView: View {
    let state: JusticePresenceState
    var compact = false

    @State private var pulse = false
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        VStack(spacing: compact ? 5 : 9) {
            ZStack {
                Circle()
                    .stroke(JafarPalette.accent.opacity(0.16), lineWidth: 1)
                    .frame(width: outerSize, height: outerSize)
                    .scaleEffect(pulseScale)
                    .opacity(pulseOpacity)

                Circle()
                    .fill(JafarPalette.accentSoft)
                    .frame(width: innerSize, height: innerSize)
                    .overlay {
                        Circle()
                            .stroke(JafarPalette.accent.opacity(0.36), lineWidth: 1)
                    }
                        .shadow(
                        color: state == .control
                            ? JafarPalette.warning.opacity(0.24)
                            : JafarPalette.accent.opacity(0.22),
                        radius: state == .analyzing ? 18 : 10
                        )

                Image(systemName: state.systemImage)
                    .font(.system(size: compact ? 20 : 29, weight: .semibold))
                    .foregroundStyle(iconColor)
                    .rotationEffect(.degrees(state == .analyzing && pulse ? 1.5 : -1.5))
            }

            if !compact {
                Text(state.title)
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(labelColor)
                    .animation(.easeInOut(duration: 0.2), value: state)
            }
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Юстиция. \(state.title)")
        .onAppear(perform: updateAnimation)
        .onChange(of: state) { _ in
            updateAnimation()
        }
    }

    private var outerSize: CGFloat { compact ? 46 : 86 }
    private var innerSize: CGFloat { compact ? 36 : 64 }

    private var iconColor: Color {
        state == .control ? JafarPalette.warning : JafarPalette.accent
    }

    private var labelColor: Color {
        state == .control ? JafarPalette.warning : JafarPalette.secondaryText
    }

    private var pulseScale: CGFloat {
        guard state == .analyzing else { return 1 }
        return pulse ? 1.14 : 0.92
    }

    private var pulseOpacity: Double {
        switch state {
        case .calm:
            return 0.45
        case .analyzing:
            return pulse ? 0.15 : 0.72
        case .control:
            return 0.78
        }
    }

    private func updateAnimation() {
        pulse = false
        guard state == .analyzing, !reduceMotion else { return }
        withAnimation(
            .easeInOut(duration: 1.25)
                .repeatForever(autoreverses: true)
        ) {
            pulse = true
        }
    }
}

#Preview("Justice states") {
    HStack(spacing: 28) {
        JusticePresenceView(state: .calm)
        JusticePresenceView(state: .analyzing)
        JusticePresenceView(state: .control)
    }
    .padding(30)
    .background(JafarPalette.background)
}
