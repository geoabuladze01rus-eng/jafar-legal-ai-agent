import SwiftUI

struct DocumentSummary: Identifiable {
    let id: String
    let title: String
    let documentType: String
    let receivedAt: Date
    let text: String
    let analysis: String
    let risks: [String]
    let proposedActions: [String]
}

struct DocumentAnalysisView: View {
    let document: DocumentSummary

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                VStack(alignment: .leading, spacing: 6) {
                    Text(document.title).font(.title2.bold())
                    Text(document.documentType).foregroundStyle(.secondary)
                    Text(document.receivedAt, style: .date).font(.caption)
                }

                AnalysisCard(title: "Юридический анализ", icon: "text.book.closed") {
                    Text(document.analysis)
                }

                AnalysisCard(title: "Риски и важные моменты", icon: "exclamationmark.shield") {
                    ForEach(document.risks, id: \.self) { risk in
                        Label(risk, systemImage: "exclamationmark.circle")
                    }
                }

                AnalysisCard(title: "Предлагаемые действия", icon: "checkmark.circle") {
                    ForEach(document.proposedActions, id: \.self) { action in
                        Label(action, systemImage: "arrow.right.circle")
                    }
                }

                DisclosureGroup("Текст документа") {
                    Text(document.text)
                        .font(.body)
                        .textSelection(.enabled)
                        .padding(.top, 8)
                }
            }
            .padding()
        }
        .navigationTitle("Документ")
    }
}

private struct AnalysisCard<Content: View>: View {
    let title: String
    let icon: String
    @ViewBuilder let content: Content

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Label(title, systemImage: icon).font(.headline)
            content
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding()
        .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 18))
    }
}
