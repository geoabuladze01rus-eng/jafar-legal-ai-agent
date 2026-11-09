import SwiftUI

// Local-only records; no sensitive draft content is written to UserDefaults.
struct JusticiaSavedDraftSummaryDTO: Decodable, Identifiable {
    let draftID: String
    let matterID: String
    let revision: Int
    let createdAt: String
    let updatedAt: String
    let kind: String
    let label: String

    var id: String { draftID }

    enum CodingKeys: String, CodingKey {
        case draftID = "draft_id"
        case matterID = "matter_id"
        case revision
        case createdAt = "created_at"
        case updatedAt = "updated_at"
        case kind, label
    }
}

struct JusticiaSavedDraftVersionDTO: Decodable {
    let draftID: String
    let matterID: String
    let revision: Int
    let createdAt: String
    let savedAt: String
    let draft: JusticiaDraftRequestDTO

    enum CodingKeys: String, CodingKey {
        case draftID = "draft_id"
        case matterID = "matter_id"
        case revision
        case createdAt = "created_at"
        case savedAt = "saved_at"
        case draft
    }
}

struct JusticiaSavedDraftRevisionInfoDTO: Decodable, Identifiable {
    let revision: Int
    let savedAt: String
    var id: Int { revision }

    enum CodingKeys: String, CodingKey {
        case revision
        case savedAt = "saved_at"
    }
}

struct JusticiaSavedDraftUpdateDTO: Encodable {
    let expectedRevision: Int
    let draft: JusticiaDraftRequestDTO

    enum CodingKeys: String, CodingKey {
        case expectedRevision = "expected_revision"
        case draft
    }
}

struct JusticiaSavedDraftRestoreDTO: Encodable {
    let expectedRevision: Int
    let sourceRevision: Int
    let approved: Bool

    enum CodingKeys: String, CodingKey {
        case expectedRevision = "expected_revision"
        case sourceRevision = "source_revision"
        case approved
    }
}

struct JusticiaDraftHistoryPanel: View {
    let matterID: String?
    let apiClient: JusticiaAPIClient?
    let draft: JusticiaDraftRequestDTO
    let inputSignature: String
    let onLoad: (JusticiaDraftRequestDTO) -> Void

    @State private var savedDrafts: [JusticiaSavedDraftSummaryDTO] = []
    @State private var versions: [JusticiaSavedDraftRevisionInfoDTO] = []
    @State private var draftID: String?
    @State private var activeMatterID: String?
    @State private var revision: Int?
    @State private var viewingRevision: JusticiaSavedDraftVersionDTO?
    @State private var busy = false
    @State private var conflict = false
    @State private var skipNextChange = false
    @State private var lastSavedSignature: String?
    @State private var statusText: String?
    @State private var errorText: String?
    @State private var autosaveTask: Task<Void, Never>?
    @State private var awaitingRestore = false

    private var canWrite: Bool {
        apiClient != nil && matterID != nil && !busy && !conflict
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Label("Локальные черновики и история редакций", systemImage: "externaldrive.badge.person.crop")
                    .font(.headline)
                Spacer()
                if let revision {
                    Text("Редакция \(revision)")
                        .font(.caption.monospacedDigit())
                        .foregroundStyle(JusticiaTheme.secondaryInk)
                }
            }

            Text("Текст хранится в зашифрованной базе только на этом Mac. После первого сохранения изменения записываются автоматически. Каждая редакция остаётся доступной.")
                .font(.caption)
                .foregroundStyle(JusticiaTheme.secondaryInk)

            HStack(spacing: 10) {
                Button {
                    Task { await saveCurrent() }
                } label: {
                    Label("Сохранить черновик", systemImage: "square.and.arrow.down")
                }
                .disabled(!canWrite)

                if !savedDrafts.isEmpty {
                    Menu("Открыть сохранённый") {
                        ForEach(savedDrafts) { item in
                            Button("\(item.label) · ред. \(item.revision)") {
                                Task { await loadDraft(item.draftID) }
                            }
                        }
                    }
                    .disabled(busy)
                }
                Button("Новый черновик") {
                    detach()
                }
                .disabled(busy)
            }
            .buttonStyle(.bordered)

            if conflict {
                Label("Обнаружена более новая редакция. Текущий текст не перезаписан. Откройте сохранённый черновик или скопируйте свои правки в новый.", systemImage: "exclamationmark.triangle.fill")
                    .font(.caption)
                    .foregroundStyle(JusticiaTheme.red)
            }

            if let draftID, !versions.isEmpty {
                VStack(alignment: .leading, spacing: 5) {
                    Text("История сохранений")
                        .font(.subheadline.weight(.semibold))
                    HStack(spacing: 8) {
                        ForEach(versions.prefix(8)) { item in
                            Button("№ \(item.revision)") {
                                Task { await viewRevision(draftID, item.revision) }
                            }
                            .buttonStyle(.bordered)
                            .controlSize(.small)
                            .disabled(busy)
                        }
                    }
                }
            }

            if let viewingRevision {
                VStack(alignment: .leading, spacing: 7) {
                    Text("Просмотр редакции № \(viewingRevision.revision)")
                        .font(.subheadline.weight(.semibold))
                    Text(viewingRevision.draft.position.isEmpty
                         ? "Обстоятельства в этой редакции не заполнены."
                         : viewingRevision.draft.position)
                        .font(.caption)
                        .textSelection(.enabled)
                    Button("Восстановить эту редакцию") {
                        awaitingRestore = true
                    }
                    .disabled(busy || conflict)
                    .buttonStyle(.bordered)
                    .confirmationDialog(
                        "Создать новую редакцию из выбранной версии?",
                        isPresented: $awaitingRestore
                    ) {
                        Button("Восстановить") {
                            Task { await restore(viewingRevision.revision) }
                        }
                        Button("Отмена", role: .cancel) {}
                    } message: {
                        Text("Старые редакции сохранятся. Текущий текст редактора будет заменён после подтверждения.")
                    }
                }
                .padding(10)
                .background(JusticiaTheme.surfaceMuted)
                .clipShape(RoundedRectangle(cornerRadius: 8))
            }

            if busy { ProgressView("Сохраняем черновик…") }
            if let statusText {
                Text(statusText)
                    .font(.caption)
                    .foregroundStyle(JusticiaTheme.green)
            }
            if let errorText {
                Text(errorText)
                    .font(.caption)
                    .foregroundStyle(JusticiaTheme.red)
            }
        }
        .padding(12)
        .background(JusticiaTheme.surfaceMuted.opacity(0.65))
        .clipShape(RoundedRectangle(cornerRadius: 12))
        .task(id: matterID) {
            autosaveTask?.cancel()
            detach()
            await loadIndex()
        }
        .onChange(of: inputSignature) { _, newValue in
            if skipNextChange {
                skipNextChange = false
                lastSavedSignature = newValue
                return
            }
            scheduleAutosave(newValue)
        }
        .onDisappear { autosaveTask?.cancel() }
    }

    @MainActor
    private func detach() {
        autosaveTask?.cancel()
        draftID = nil
        activeMatterID = nil
        revision = nil
        versions = []
        viewingRevision = nil
        conflict = false
        lastSavedSignature = nil
        errorText = nil
        statusText = nil
    }

    @MainActor
    private func loadIndex() async {
        guard let apiClient, let matterID else { return }
        do {
            let items = try await apiClient.listSavedDrafts(matterID: matterID)
            if self.matterID == matterID { savedDrafts = items }
        } catch {
            if self.matterID == matterID { errorText = error.localizedDescription }
        }
    }

    @MainActor
    private func loadDraft(_ selectedID: String) async {
        guard let apiClient, let matterID else { return }
        autosaveTask?.cancel()
        busy = true
        errorText = nil
        defer { busy = false }
        do {
            let saved = try await apiClient.readSavedDraft(matterID: matterID, draftID: selectedID)
            guard self.matterID == matterID, saved.matterID == matterID else { return }
            skipNextChange = true
            onLoad(saved.draft)
            draftID = saved.draftID
            activeMatterID = matterID
            revision = saved.revision
            viewingRevision = nil
            conflict = false
            lastSavedSignature = nil
            statusText = "Редакция \(saved.revision) загружена для работы."
            await loadVersions()
            settleLoadedState()
        } catch {
            errorText = error.localizedDescription
        }
    }

    @MainActor
    private func saveCurrent() async {
        guard let apiClient, let matterID, !busy, !conflict else { return }
        let payload = draft
        let signature = inputSignature
        let originalDraftID = draftID
        let originalRevision = revision
        busy = true
        errorText = nil
        defer { busy = false }
        do {
            let saved: JusticiaSavedDraftVersionDTO
            if let originalDraftID, let originalRevision, activeMatterID == matterID {
                saved = try await apiClient.updateSavedDraft(
                    matterID: matterID, draftID: originalDraftID,
                    expectedRevision: originalRevision, draft: payload
                )
            } else {
                saved = try await apiClient.createSavedDraft(matterID: matterID, draft: payload)
            }
            guard self.matterID == matterID else { return }
            draftID = saved.draftID
            activeMatterID = matterID
            revision = saved.revision
            lastSavedSignature = signature
            viewingRevision = nil
            statusText = "Сохранена редакция № \(saved.revision)."
            await loadIndex()
            await loadVersions()
            if inputSignature != signature {
                scheduleAutosave(inputSignature)
            }
        } catch {
            if let apiError = error as? JusticiaAPIError,
               case .httpStatus(409, _) = apiError {
                conflict = true
            }
            errorText = error.localizedDescription
        }
    }

    @MainActor
    private func loadVersions() async {
        guard let apiClient, let matterID, let draftID, activeMatterID == matterID else { return }
        do {
            versions = try await apiClient.savedDraftRevisions(matterID: matterID, draftID: draftID)
        } catch {
            errorText = error.localizedDescription
        }
    }

    @MainActor
    private func viewRevision(_ selectedID: String, _ selectedVersion: Int) async {
        guard let apiClient, let matterID, activeMatterID == matterID else { return }
        do {
            let item = try await apiClient.readSavedDraftRevision(
                matterID: matterID, draftID: selectedID, revision: selectedVersion
            )
            if self.matterID == matterID && item.draftID == draftID {
                viewingRevision = item
            }
        } catch {
            errorText = error.localizedDescription
        }
    }

    @MainActor
    private func restore(_ sourceVersion: Int) async {
        guard let apiClient, let matterID, let draftID, let revision,
              activeMatterID == matterID, !busy, !conflict else { return }
        autosaveTask?.cancel()
        busy = true
        defer { busy = false }
        do {
            let restored = try await apiClient.restoreSavedDraftRevision(
                matterID: matterID, draftID: draftID,
                expectedRevision: revision, sourceRevision: sourceVersion
            )
            guard self.matterID == matterID, restored.matterID == matterID else { return }
            skipNextChange = true
            onLoad(restored.draft)
            self.revision = restored.revision
            conflict = false
            viewingRevision = nil
            statusText = "Редакция № \(sourceVersion) восстановлена как новая № \(restored.revision)."
            await loadVersions()
            await loadIndex()
            settleLoadedState()
        } catch {
            if let apiError = error as? JusticiaAPIError,
               case .httpStatus(409, _) = apiError { conflict = true }
            errorText = error.localizedDescription
        }
    }

    @MainActor
    private func settleLoadedState() {
        // If loading a saved revision did not change the rendered form,
        // the next real user edit must not be accidentally suppressed.
        Task { @MainActor in
            await Task.yield()
            skipNextChange = false
            lastSavedSignature = inputSignature
        }
    }

    @MainActor
    private func scheduleAutosave(_ signature: String) {
        autosaveTask?.cancel()
        guard let draftID, let revision, let matterID,
              activeMatterID == matterID, revision > 0,
              !conflict, lastSavedSignature != signature, !busy else { return }
        _ = draftID
        autosaveTask = Task { @MainActor in
            do {
                try await Task.sleep(nanoseconds: 1_200_000_000)
                if !Task.isCancelled && self.matterID == matterID && self.inputSignature == signature {
                    await saveCurrent()
                }
            } catch {
                // Superseded by a newer edit; do not overwrite an unsaved revision.
            }
        }
    }
}
