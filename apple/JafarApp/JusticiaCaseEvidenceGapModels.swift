import Foundation

struct JusticiaGroundedStatementDTO: Codable, Identifiable, Hashable {
    let statementID: String
    let category: String
    let documentID: String
    let filename: String
    let citation: String
    let quote: String
    let statement: String
    let subject: String
    let physicalPage: Int?

    var id: String { statementID }

    enum CodingKeys: String, CodingKey {
        case statementID = "statement_id"
        case category
        case documentID = "document_id"
        case filename, citation, quote, statement, subject
        case physicalPage = "physical_page"
    }
}

struct JusticiaGroundedEvidenceGapDTO: Codable, Identifiable, Hashable {
    let gapID: String
    let topic: String
    let description: String
    let expectedEvidence: [String]
    let severity: String
    let relatedCitation: String?
    let suggestedAction: String

    var id: String { gapID }

    enum CodingKeys: String, CodingKey {
        case gapID = "gap_id"
        case topic, description
        case expectedEvidence = "expected_evidence"
        case severity
        case relatedCitation = "related_citation"
        case suggestedAction = "suggested_action"
    }
}

struct JusticiaCaseEvidenceGapReportDTO: Codable {
    let matterID: String
    let matterTitle: String
    let caseNumber: String?
    let statements: [JusticiaGroundedStatementDTO]
    let gaps: [JusticiaGroundedEvidenceGapDTO]
    let summary: String
    let warnings: [String]

    enum CodingKeys: String, CodingKey {
        case matterID = "matter_id"
        case matterTitle = "matter_title"
        case caseNumber = "case_number"
        case statements, gaps, summary, warnings
    }
}
