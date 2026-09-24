import SwiftUI

struct JusticiaGlobalSearchView: View {
    @Environment(\.dismiss) private var dismiss
    @Binding var query: String
    @ObservedObject var workspace: JusticiaWorkspaceStore

    let onMatter: (JusticiaMatterDTO) -> Void
    let onDocument: (JusticiaDocumentDTO) -> Void
    let onSection: (JusticiaSection) -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                VStack(alignment: .leading, spacing: 3) {
                    Text("Поиск")
                        .font(.title2.bold())
                    Text("Дела, документы выбранного дела и разделы «Юстиции».")
                        .font(.caption)
                        .foregroundStyle(JusticiaTheme.secondaryInk)
                }
                Spacer()
                Button {
                    dismiss()
                } label: {
                    Image(systemName: "xmark")
                }
                .buttonStyle(.plain)
            }

            HStack(spacing: 9) {
                Image(systemName: "magnifyingglass")
                    .foregroundStyle(JusticiaTheme.secondaryInk)
                TextField("Введите название, номер дела или документ", text: $query)
                    .textFieldStyle(.plain)
                if !query.isEmpty {
                    Button {
                        query = ""
                    } label: {
                        Image(systemName: "xmark.circle.fill")
                            .foregroundStyle(JusticiaTheme.secondaryInk)
                    }
                    .buttonStyle(.plain)
                }
            }
            .padding(.horizontal, 12)
            .frame(height: 40)
            .background(JusticiaTheme.surfaceMuted)
            .clipShape(RoundedRectangle(cornerRadius: 10))

            if normalizedQuery.isEmpty {
                emptyHint
            } else if matterResults.isEmpty && documentResults.isEmpty && sectionResults.isEmpty {
                VStack(spacing: 10) {
                    JusticiaIconTile(systemName: "magnifyingglass", color: JusticiaTheme.secondaryInk)
                    Text("Ничего не найдено")
                        .font(.headline)
                    Text("Попробуйте номер дела, фамилию, название документа или раздел приложения.")
                        .font(.caption)
                        .foregroundStyle(JusticiaTheme.secondaryInk)
                        .multilineTextAlignment(.center)
                }
                .frame(maxWidth: .infinity, minHeight: 240)
            } else {
                ScrollView {
                    VStack(alignment: .leading, spacing: 18) {
                        if !matterResults.isEmpty {
                            resultSectionTitle("Дела", count: matterResults.count)
                            ForEach(matterResults.prefix(8)) { matter in
                                Button {
                                    onMatter(matter)
                                    dismiss()
                                } label: {
                                    HStack(spacing: 11) {
                                        JusticiaIconTile(systemName: "briefcase", color: JusticiaTheme.blue, size: 32)
                                        VStack(alignment: .leading, spacing: 2) {
                                            Text(matter.displayNumber)
                                                .font(.subheadline.weight(.semibold))
                                                .foregroundStyle(JusticiaTheme.ink)
                                            Text(matter.title)
                                                .font(.caption)
                                                .foregroundStyle(JusticiaTheme.secondaryInk)
                                                .lineLimit(1)
                                        }
                                        Spacer()
                                        Image(systemName: "chevron.right")
                                            .font(.caption)
                                            .foregroundStyle(JusticiaTheme.secondaryInk)
                                    }
                                    .padding(10)
                                    .background(JusticiaTheme.surfaceMuted.opacity(0.65))
                                    .clipShape(RoundedRectangle(cornerRadius: 10))
                                }
                                .buttonStyle(.plain)
                            }
                        }

                        if !documentResults.isEmpty {
                            resultSectionTitle("Документы выбранного дела", count: documentResults.count)
                            ForEach(documentResults.prefix(8)) { document in
                                Button {
                                    onDocument(document)
                                    dismiss()
                                } label: {
                                    HStack(spacing: 11) {
                                        JusticiaIconTile(systemName: "doc.text", color: JusticiaTheme.violet, size: 32)
                                        VStack(alignment: .leading, spacing: 2) {
                                            Text(document.filename)
                                                .font(.subheadline.weight(.semibold))
                                                .foregroundStyle(JusticiaTheme.ink)
                                            Text(document.displayState)
                                                .font(.caption)
                                                .foregroundStyle(JusticiaTheme.secondaryInk)
                                        }
                                        Spacer()
                                        Image(systemName: "chevron.right")
                                            .font(.caption)
                                            .foregroundStyle(JusticiaTheme.secondaryInk)
                                    }
                                    .padding(10)
                                    .background(JusticiaTheme.surfaceMuted.opacity(0.65))
                                    .clipShape(RoundedRectangle(cornerRadius: 10))
                                }
                                .buttonStyle(.plain)
                            }
                        }

                        if !sectionResults.isEmpty {
                            resultSectionTitle("Разделы", count: sectionResults.count)
                            ForEach(sectionResults) { section in
                                Button {
                                    onSection(section)
                                    dismiss()
                                } label: {
                                    HStack(spacing: 11) {
                                        JusticiaIconTile(systemName: section.icon, color: JusticiaTheme.green, size: 32)
                                        Text(section.rawValue)
                                            .font(.subheadline.weight(.semibold))
                                            .foregroundStyle(JusticiaTheme.ink)
                                        Spacer()
                                        Image(systemName: "chevron.right")
                                            .font(.caption)
                                            .foregroundStyle(JusticiaTheme.secondaryInk)
                                    }
                                    .padding(10)
                                    .background(JusticiaTheme.surfaceMuted.opacity(0.65))
                                    .clipShape(RoundedRectangle(cornerRadius: 10))
                                }
                                .buttonStyle(.plain)
                            }
                        }
                    }
                }
            }

            Spacer(minLength: 0)
        }
        .padding(22)
        .background(JusticiaTheme.canvas)
    }

    private var normalizedQuery: String {
        query.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
    }

    private var matterResults: [JusticiaMatterDTO] {
        guard !normalizedQuery.isEmpty else { return [] }
        return workspace.matters.filter { matter in
            matter.title.lowercased().contains(normalizedQuery)
                || matter.displayNumber.lowercased().contains(normalizedQuery)
                || (matter.clientName?.lowercased().contains(normalizedQuery) ?? false)
                || (matter.opposingParty?.lowercased().contains(normalizedQuery) ?? false)
                || matter.displayCourt.lowercased().contains(normalizedQuery)
        }
    }

    private var documentResults: [JusticiaDocumentDTO] {
        guard !normalizedQuery.isEmpty else { return [] }
        return workspace.documents.filter {
            $0.filename.lowercased().contains(normalizedQuery)
                || $0.mediaType.lowercased().contains(normalizedQuery)
        }
    }

    private var sectionResults: [JusticiaSection] {
        guard !normalizedQuery.isEmpty else { return [] }
        return JusticiaSection.allCases.filter {
            $0.rawValue.lowercased().contains(normalizedQuery)
        }
    }

    private var emptyHint: some View {
        VStack(spacing: 10) {
            JusticiaIconTile(systemName: "command", color: JusticiaTheme.blue)
            Text("Единый поиск по рабочему пространству")
                .font(.headline)
            Text("Поиск не отправляет запрос в облако: он работает по уже загруженным локальным данным интерфейса.")
                .font(.caption)
                .foregroundStyle(JusticiaTheme.secondaryInk)
                .multilineTextAlignment(.center)
                .frame(maxWidth: 480)
        }
        .frame(maxWidth: .infinity, minHeight: 240)
    }

    private func resultSectionTitle(_ title: String, count: Int) -> some View {
        HStack {
            Text(title)
                .font(.headline)
            Spacer()
            JusticiaPill(text: "\(count)", color: JusticiaTheme.blue)
        }
    }
}
