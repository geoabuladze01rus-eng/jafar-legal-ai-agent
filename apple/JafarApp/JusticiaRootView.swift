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
    @State private var showingSearchResults = false
    @State private var showingNotifications = false
    @State private var showingCreateMatter = false
    @AppStorage("justicia.profileAvatar") private var avatarData = Data()
    @AppStorage("justicia.compactSidebar") private var compactSidebar = false
    @AppStorage("justicia.notifications") private var notificationsEnabled = true
    @AppStorage("justicia.reduceMotion") private var reduceMotion = false
    @AppStorage("justicia.onboardingCompleted") private var onboardingCompleted = false

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
        ZStack {
            HStack(spacing: 0) {
                sidebar

                VStack(spacing: 0) {
                    topBar
                    Divider().overlay(JusticiaTheme.border.opacity(0.8))

                    ZStack {
                        JusticiaTheme.canvas.ignoresSafeArea()

                        ScrollView {
                            VStack(spacing: 18) {
                                if let backendStatusText, apiClient == nil {
                                    JusticiaBackendBanner(
                                        text: backendStatusText,
                                        failed: backendFailed,
                                        retry: retryBackend
                                    )
                                }

                                content
                                    .transition(.opacity)
                            }
                            .padding(26)
                            .frame(maxWidth: 1380)
                            .frame(maxWidth: .infinity, alignment: .top)
                        }
                    }
                }
            }
            .background(JusticiaTheme.canvas)

            if !onboardingCompleted {
                JusticiaOnboardingView()
                    .transition(.opacity)
                    .zIndex(10)
            }
        }
        .preferredColorScheme(.light)
        .tint(JusticiaTheme.blue)
        .animation(reduceMotion ? nil : .easeInOut(duration: 0.20), value: selectedSection)
        .sheet(isPresented: $showingCreateMatter) {
            JusticiaCreateMatterSheet(workspace: workspace, onCreated: { selectedSection = .matters })
                .frame(minWidth: 520, minHeight: 560)
        }
        .sheet(isPresented: $showingNotifications) {
            JusticiaNotificationsView(workspace: workspace)
                .frame(minWidth: 420, minHeight: 360)
        }
        .sheet(isPresented: $showingSearchResults) {
            JusticiaGlobalSearchView(
                query: $searchText,
                workspace: workspace,
                onMatter: { matter in
                    Task {
                        await workspace.selectMatter(matter)
                        selectedSection = .matters
                    }
                },
                onDocument: { document in
                    workspace.selectedDocumentID = document.id
                    selectedSection = .documents
                },
                onSection: { section in
                    selectedSection = section
                }
            )
            .frame(minWidth: 620, minHeight: 520)
        }
        .task {
            workspace.configure(client: apiClient)
            await workspace.refresh()
        }
    }

    private var sidebar: some View {
        VStack(alignment: .leading, spacing: 18) {
            sidebarBrand
            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    navigationGroup("Рабочее пространство", sections: [
                        .home, .matters, .documents, .analytics, .deadlines, .templates
                    ])
                    navigationGroup("Инструменты", sections: [
                        .publishing, .transcription, .settings
                    ])
                }
                .padding(.horizontal, 10)
            }
            .scrollIndicators(.hidden)

            Button {
                selectedSection = .settings
            } label: {
                HStack(spacing: 10) {
                    JusticiaAvatar(data: avatarData, size: 34)
                    if !compactSidebar {
                        VStack(alignment: .leading, spacing: 3) {
                            Text("Профиль юриста")
                                .font(.caption.weight(.semibold))
                                .foregroundStyle(JusticiaTheme.sidebarInk)
                            Text("Настройки")
                                .font(.caption2)
                                .foregroundStyle(JusticiaTheme.sidebarMuted)
                        }
                        Spacer(minLength: 0)
                        Image(systemName: "chevron.right")
                            .font(.caption2)
                            .foregroundStyle(JusticiaTheme.sidebarMuted)
                    }
                }
                .padding(.horizontal, 10)
                .padding(.vertical, 9)
                .frame(maxWidth: .infinity)
                .background(Color.white.opacity(0.07), in: RoundedRectangle(cornerRadius: 10))
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            .accessibilityLabel("Настройки профиля")
            .help("Настройки профиля")
            .padding(.horizontal, 12)
            .padding(.bottom, 14)
        }
        .frame(width: compactSidebar ? 78 : JusticiaTheme.sidebarWidth)
        .background(JusticiaTheme.sidebar)
    }

    private var sidebarBrand: some View {
        HStack(spacing: 11) {
            JusticiaScalesMark()
                .stroke(JusticiaTheme.brass, style: StrokeStyle(lineWidth: 1.35, lineCap: .round, lineJoin: .round))
                .frame(width: 26, height: 26)
                .frame(width: 40, height: 40)
                .background(JusticiaTheme.brass.opacity(0.1), in: RoundedRectangle(cornerRadius: 10))
                .overlay {
                    RoundedRectangle(cornerRadius: 10).strokeBorder(JusticiaTheme.brass.opacity(0.24))
                }
                .accessibilityHidden(true)

            if !compactSidebar {
                VStack(alignment: .leading, spacing: 3) {
                    Text("Юстиция")
                        .font(.system(size: 25, weight: .semibold, design: .serif))
                        .foregroundStyle(JusticiaTheme.sidebarInk)
                    Text("ИИ-помощник юриста")
                        .font(.caption2)
                        .foregroundStyle(JusticiaTheme.sidebarMuted)
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: compactSidebar ? .center : .leading)
        .padding(.horizontal, 16)
        .padding(.top, 20)
    }

    private func navigationGroup(_ title: String, sections: [JusticiaSection]) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            if !compactSidebar {
                Text(title.uppercased())
                    .font(.system(size: 9, weight: .semibold))
                    .tracking(1.25)
                    .foregroundStyle(JusticiaTheme.sidebarMuted)
                    .padding(.leading, 13)
                    .padding(.bottom, 4)
            }
            ForEach(sections) { section in
                let isSelected = selectedSection == section
                let title = section == .transcription ? "Транскрибация" : section.rawValue
                Button {
                    selectedSection = section
                } label: {
                    HStack(spacing: 10) {
                        Image(systemName: section.icon)
                            .font(.system(size: 14, weight: .medium))
                            .foregroundStyle(isSelected ? JusticiaTheme.brass : JusticiaTheme.sidebarMuted)
                            .frame(width: 19)
                        if !compactSidebar {
                            Text(title)
                                .font(.system(size: 13, weight: isSelected ? .semibold : .regular))
                                .lineLimit(1)
                        }
                    }
                    .padding(.horizontal, 12)
                    .frame(maxWidth: .infinity, alignment: compactSidebar ? .center : .leading)
                    .frame(height: 36)
                    .foregroundStyle(JusticiaTheme.sidebarInk)
                    .background(
                        Color.white.opacity(isSelected ? 0.09 : 0), in: RoundedRectangle(cornerRadius: 8)
                    )
                    .overlay(alignment: .leading) {
                        if isSelected {
                            Capsule()
                                .fill(JusticiaTheme.brass)
                                .frame(width: 2, height: 16)
                                .padding(.leading, 2)
                        }
                    }
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .accessibilityLabel(title)
                .accessibilityAddTraits(isSelected ? .isSelected : [])
                .help(title)
            }
        }
    }

    private var topBar: some View {
        HStack(spacing: 14) {
            HStack(spacing: 9) {
                Image(systemName: "magnifyingglass")
                    .foregroundStyle(JusticiaTheme.secondaryInk)
                TextField("Поиск по делам, документам и разделам…", text: $searchText)
                    .textFieldStyle(.plain)
                    .onSubmit {
                        if !searchText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                            showingSearchResults = true
                        }
                    }
                if !searchText.isEmpty {
                    Button {
                        showingSearchResults = true
                    } label: {
                        Image(systemName: "arrow.right.circle.fill")
                            .foregroundStyle(JusticiaTheme.blue)
                    }
                    .buttonStyle(.plain)

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

            if apiClient != nil {
                Label("Локальный режим", systemImage: "checkmark.shield")
                    .font(.caption.weight(.medium))
                    .foregroundStyle(JusticiaTheme.secondaryInk)
                    .fixedSize()
                    .help("Локальный движок готов")
            }

            if notificationsEnabled {
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
            }

            Button {
                selectedSection = .settings
            } label: {
                HStack(spacing: 8) {
                    JusticiaAvatar(data: avatarData, size: 33)
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
            .accessibilityLabel("Настройки профиля")
            .help("Настройки профиля")
        }
        .padding(.horizontal, 20)
        .frame(height: 62)
        .background(JusticiaTheme.surface)
    }

    @ViewBuilder
    private var content: some View {
        switch selectedSection {
        case .home:
            JusticiaLiveHomeView(workspace: workspace,
                navigate: { selectedSection = $0 },
                canCreateMatter: apiClient != nil,
                createMatter: { showingCreateMatter = true }
            )
        case .matters:
            JusticiaLiveMattersView(
                workspace: workspace,
                apiClient: apiClient,
                createMatter: { showingCreateMatter = true },
                openDocument: { documentID in
                    workspace.selectedDocumentID = documentID
                    selectedSection = .documents
                }
            )
        case .documents:
            JusticiaLiveDocumentsView(workspace: workspace)
        case .analytics:
            VStack(alignment: .leading, spacing: 20) {
                JusticiaLiveAnalyticsView(workspace: workspace)
                JusticiaEvidenceMatrixView(workspace: workspace, apiClient: apiClient)
                JusticiaClaimReviewView(workspace: workspace, apiClient: apiClient)
            }
        case .deadlines:
            JusticiaLiveDeadlinesView(workspace: workspace)
        case .templates:
            VStack(alignment: .leading, spacing: 20) {
                JusticiaDraftComposerView(workspace: workspace, apiClient: apiClient)
                JusticiaTemplatesWorkspaceView()
            }
        case .publishing:
            JusticiaPublishingWorkspaceView()
        case .transcription:
            JusticiaLiveTranscriptionView(voice: voice, workspace: workspace)
        case .settings:
            JusticiaSettingsView(avatarData: $avatarData)
        }
    }
}

struct JusticiaScalesMark: Shape {
    func path(in rect: CGRect) -> Path {
        func point(_ x: CGFloat, _ y: CGFloat) -> CGPoint {
            CGPoint(x: rect.minX + rect.width * x, y: rect.minY + rect.height * y)
        }
        var path = Path()
        path.move(to: point(0.50, 0.10))
        path.addLine(to: point(0.50, 0.85))
        path.move(to: point(0.30, 0.85))
        path.addLine(to: point(0.70, 0.85))
        path.move(to: point(0.15, 0.27))
        path.addLine(to: point(0.85, 0.27))
        for x in [CGFloat(0.24), CGFloat(0.76)] {
            path.move(to: point(x, 0.27))
            path.addLine(to: point(x - 0.14, 0.60))
            path.addQuadCurve(to: point(x + 0.14, 0.60), control: point(x, 0.82))
            path.closeSubpath()
        }
        return path
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
