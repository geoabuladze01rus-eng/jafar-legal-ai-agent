import SwiftUI

struct JusticiaRootView: View {
    @ObservedObject var voice: VoiceSessionViewModel
    private let apiClient: JusticiaAPIClient?
    var backendStatusText: String?
    var backendFailed: Bool
    var retryBackend: (() -> Void)?

    @StateObject private var workspace: JusticiaWorkspaceStore
    @State private var selectedSection: JusticiaSection = .home
    @State private var searchText = ""
    @State private var showingNotifications = false

    init(
        voice: VoiceSessionViewModel,
        apiClient: JusticiaAPIClient? = nil,
        backendStatusText: String? = nil,
        backendFailed: Bool = false,
        retryBackend: (() -> Void)? = nil
    ) {
        self.voice = voice
        self.apiClient = apiClient
        self.backendStatusText = backendStatusText
        self.backendFailed = backendFailed
        self.retryBackend = retryBackend
        _workspace = StateObject(wrappedValue: JusticiaWorkspaceStore(client: apiClient))
    }

    var body: some View {
        HStack(spacing: 0) {
            sidebar
            Divider().overlay(JusticiaTheme.border)

            VStack(spacing: 0) {
                topBar
                Divider().overlay(JusticiaTheme.border.opacity(0.8))

                ZStack {
                    JusticiaTheme.canvas.ignoresSafeArea()

                    ScrollView {
                        VStack(spacing: 18) {
                            if let backendStatusText {
                                JusticiaBackendBanner(
                                    text: backendStatusText,
                                    failed: backendFailed,
                                    retry: retryBackend
                                )
                            }

                            content
                                .transition(.opacity.combined(with: .move(edge: .trailing)))
                        }
                        .padding(22)
                        .frame(maxWidth: 1480)
                        .frame(maxWidth: .infinity, alignment: .top)
                    }
                }
            }
        }
        .background(JusticiaTheme.canvas)
        .preferredColorScheme(.light)
        .animation(.easeInOut(duration: 0.20), value: selectedSection)
        .sheet(isPresented: $showingNotifications) {
            JusticiaNotificationsView(workspace: workspace)
                .frame(minWidth: 420, minHeight: 360)
        }
        .task {
            workspace.configure(client: apiClient)
            await workspace.refresh()
        }
    }

    private var sidebar: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack(spacing: 11) {
                ZStack {
                    RoundedRectangle(cornerRadius: 12, style: .continuous)
                        .fill(JusticiaTheme.gold.opacity(0.12))
                    Image(systemName: "scalemass")
                        .font(.system(size: 23, weight: .semibold))
                        .foregroundStyle(JusticiaTheme.gold)
                }
                .frame(width: 42, height: 42)

                VStack(alignment: .leading, spacing: 1) {
                    Text("Юстиция")
                        .font(.system(size: 24, weight: .bold, design: .serif))
                        .foregroundStyle(JusticiaTheme.ink)
                    Text("ИИ-помощник юриста")
                        .font(.caption)
                        .foregroundStyle(JusticiaTheme.secondaryInk)
                }
            }
            .padding(.horizontal, 16)
            .padding(.top, 16)

            VStack(spacing: 4) {
                ForEach(JusticiaSection.allCases) { section in
                    Button {
                        selectedSection = section
                    } label: {
                        HStack(spacing: 12) {
                            Image(systemName: section.icon)
                                .font(.system(size: 15, weight: .medium))
                                .frame(width: 20)
                            Text(section.rawValue)
                                .font(.system(size: 14, weight: selectedSection == section ? .semibold : .regular))
                                .lineLimit(1)
                            Spacer()
                        }
                        .foregroundStyle(selectedSection == section ? JusticiaTheme.blue : JusticiaTheme.ink)
                        .padding(.horizontal, 13)
                        .frame(height: 42)
                        .background(
                            RoundedRectangle(cornerRadius: 10, style: .continuous)
                                .fill(selectedSection == section ? JusticiaTheme.blueSoft : Color.clear)
                        )
                    }
                    .buttonStyle(.plain)
                    .accessibilityLabel(section.rawValue)
                }
            }
            .padding(.horizontal, 10)

            Spacer()

            VStack(alignment: .leading, spacing: 7) {
                HStack(spacing: 10) {
                    Circle()
                        .fill(JusticiaTheme.ink)
                        .frame(width: 34, height: 34)
                        .overlay(
                            Text("Ю")
                                .foregroundStyle(.white)
                                .font(.caption.bold())
                        )
                    VStack(alignment: .leading, spacing: 1) {
                        Text("Профиль юриста")
                            .font(.caption.weight(.semibold))
                        Text("Локальная рабочая среда")
                            .font(.caption2)
                            .foregroundStyle(JusticiaTheme.secondaryInk)
                    }
                }

                HStack(spacing: 6) {
                    Circle()
                        .fill(JusticiaTheme.green)
                        .frame(width: 7, height: 7)
                    Text("Данные хранятся локально")
                        .font(.caption2)
                        .foregroundStyle(JusticiaTheme.secondaryInk)
                }
            }
            .padding(14)
            .background(JusticiaTheme.surface.opacity(0.85))
            .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
            .padding(12)
        }
        .frame(width: JusticiaTheme.sidebarWidth)
        .background(JusticiaTheme.sidebar)
    }

    private var topBar: some View {
        HStack(spacing: 14) {
            HStack(spacing: 9) {
                Image(systemName: "magnifyingglass")
                    .foregroundStyle(JusticiaTheme.secondaryInk)
                TextField("Поиск по делам, документам, судебной практике…", text: $searchText)
                    .textFieldStyle(.plain)
                if !searchText.isEmpty {
                    Button {
                        searchText = ""
                    } label: {
                        Image(systemName: "xmark.circle.fill")
                            .foregroundStyle(JusticiaTheme.secondaryInk.opacity(0.7))
                    }
                    .buttonStyle(.plain)
                }
            }
            .padding(.horizontal, 13)
            .frame(maxWidth: 620)
            .frame(height: 38)
            .background(JusticiaTheme.surfaceMuted)
            .clipShape(RoundedRectangle(cornerRadius: 11, style: .continuous))

            Spacer()

            Button {
                showingNotifications = true
            } label: {
                Image(systemName: "bell")
                    .font(.system(size: 15, weight: .medium))
                    .frame(width: 34, height: 34)
                    .background(JusticiaTheme.surfaceMuted)
                    .clipShape(Circle())
            }
            .buttonStyle(.plain)

            Button {
                selectedSection = .settings
            } label: {
                HStack(spacing: 8) {
                    Circle()
                        .fill(JusticiaTheme.blueSoft)
                        .frame(width: 32, height: 32)
                        .overlay(Image(systemName: "person.fill").foregroundStyle(JusticiaTheme.blue))
                    VStack(alignment: .leading, spacing: 0) {
                        Text("Юрист")
                            .font(.caption.weight(.semibold))
                            .foregroundStyle(JusticiaTheme.ink)
                        Text("Настройки профиля")
                            .font(.caption2)
                            .foregroundStyle(JusticiaTheme.secondaryInk)
                    }
                }
            }
            .buttonStyle(.plain)
        }
        .padding(.horizontal, 20)
        .frame(height: 62)
        .background(JusticiaTheme.surface)
    }

    @ViewBuilder
    private var content: some View {
        switch selectedSection {
        case .home:
            JusticiaLiveHomeView(workspace: workspace, navigate: { selectedSection = $0 })
        case .matters:
            JusticiaLiveMattersView(workspace: workspace)
        case .documents:
            JusticiaLiveDocumentsView(workspace: workspace)
        case .analytics:
            JusticiaAnalyticsView()
        case .deadlines:
            JusticiaDeadlinesView()
        case .templates:
            JusticiaTemplatesView()
        case .publishing:
            JusticiaPublishingView()
        case .transcription:
            JusticiaTranscriptionView(voice: voice)
        case .settings:
            JusticiaSettingsView()
        }
    }
}

private struct JusticiaBackendBanner: View {
    let text: String
    let failed: Bool
    let retry: (() -> Void)?

    var body: some View {
        HStack(spacing: 10) {
            Image(systemName: failed ? "exclamationmark.triangle.fill" : "checkmark.shield.fill")
                .foregroundStyle(failed ? JusticiaTheme.red : JusticiaTheme.green)
            Text(text)
                .font(.caption.weight(.semibold))
                .foregroundStyle(JusticiaTheme.ink)
            Spacer()
            if failed, let retry {
                Button("Повторить") { retry() }
                    .buttonStyle(.bordered)
                    .controlSize(.small)
            }
        }
        .padding(.horizontal, 14)
        .frame(height: 40)
        .background((failed ? JusticiaTheme.red : JusticiaTheme.green).opacity(0.07))
        .clipShape(RoundedRectangle(cornerRadius: 11, style: .continuous))
    }
}

private struct JusticiaNotificationsView: View {
    @Environment(\.dismiss) private var dismiss
    @ObservedObject var workspace: JusticiaWorkspaceStore

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            HStack {
                Text("Уведомления")
                    .font(.title2.bold())
                Spacer()
                Button {
                    dismiss()
                } label: {
                    Image(systemName: "xmark")
                }
                .buttonStyle(.plain)
            }

            if workspace.matters.isEmpty {
                VStack(spacing: 8) {
                    JusticiaIconTile(systemName: "bell.slash", color: JusticiaTheme.secondaryInk)
                    Text("Новых уведомлений нет")
                        .font(.subheadline.weight(.semibold))
                    Text("События по делам и документам будут появляться здесь.")
                        .font(.caption)
                        .foregroundStyle(JusticiaTheme.secondaryInk)
                        .multilineTextAlignment(.center)
                }
                .frame(maxWidth: .infinity, minHeight: 160)
                .justiciaCard()
            } else {
                ForEach(workspace.matters.prefix(5)) { matter in
                    HStack(alignment: .top, spacing: 12) {
                        JusticiaIconTile(systemName: matter.deadlines.isEmpty ? "briefcase" : "calendar.badge.clock", color: matter.deadlines.isEmpty ? JusticiaTheme.blue : JusticiaTheme.orange)
                        VStack(alignment: .leading, spacing: 4) {
                            Text(matter.deadlines.first?.title ?? matter.title)
                                .font(.subheadline.weight(.semibold))
                            Text(matter.displayNumber + " · " + matter.displayStatus)
                                .font(.caption)
                                .foregroundStyle(JusticiaTheme.secondaryInk)
                        }
                        Spacer()
                    }
                    .justiciaCard(padding: 12)
                }
            }

            Spacer()
        }
        .padding(22)
        .background(JusticiaTheme.canvas)
    }
}
