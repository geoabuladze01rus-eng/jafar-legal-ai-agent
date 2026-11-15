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

struct JusticiaGroundedContradictionDTO: Codable, Identifiable, Hashable {
    let contradictionID: String
    let topic: String
    let description: String
    let statementIDs: [String]
    let citations: [String]
    let documents: [String]
    let pages: [Int]
    let severity: String
    let suggestedInquiry: String

    var id: String { contradictionID }

    enum CodingKeys: String, CodingKey {
        case contradictionID = "contradiction_id"
        case topic, description
        case statementIDs = "statement_ids"
        case citations, documents, pages, severity
        case suggestedInquiry = "suggested_inquiry"
    }
}

struct JusticiaCaseEvidenceGapReportDTO: Codable {
    let matterID: String
    let matterTitle: String
    let caseNumber: String?
    let statements: [JusticiaGroundedStatementDTO]
    let gaps: [JusticiaGroundedEvidenceGapDTO]
    let contradictions: [JusticiaGroundedContradictionDTO]?
    let analysisMethodUsed: String?
    let analysisDetails: String?
    let summary: String
    let warnings: [String]

    enum CodingKeys: String, CodingKey {
        case matterID = "matter_id"
        case matterTitle = "matter_title"
        case caseNumber = "case_number"
        case statements, gaps, contradictions
        case analysisMethodUsed = "analysis_method_used"
        case analysisDetails = "analysis_details"
        case summary, warnings
    }
}
