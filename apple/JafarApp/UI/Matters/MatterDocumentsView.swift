import SwiftUI

struct MatterDocumentDTO: Codable, Identifiable, Sendable { let id: String; let matterID: String; let title: String; let documentType: String?; let source: String?; let pageCount: Int?; let processingStatus: String?; let analysisStatus: String?; enum CodingKeys: String, CodingKey { case id, matterID = "matter_id", title, documentType = "document_type", source, pageCount = "page_count", processingStatus = "processing_status", analysisStatus = "analysis_status" } }

struct MatterDocumentsView: View {
    let matterID: String
    var body: some View { JafarCard(title: "Документы") { Text("Документы по делу пока не загружены").foregroundStyle(JafarPalette.secondary); Text("Read-only document API ещё не подключён к backend.").font(.caption).foregroundStyle(JafarPalette.secondary) } }
}
