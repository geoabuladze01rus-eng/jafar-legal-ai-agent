import Foundation

struct JusticiaClaimDecisionInputDTO: Encodable {
    let candidateID: String
    let decision: String
    let note: String

    enum CodingKeys: String, CodingKey {
        case candidateID = "candidate_id"
        case decision, note
    }
}

struct JusticiaSaveClaimDecisionDTO: Encodable {
    let report: JusticiaClaimReviewReportDTO
    let decision: JusticiaClaimDecisionInputDTO
}

struct JusticiaClaimDecisionRecordDTO: Decodable, Identifiable {
    let recordID: String
    let matterID: String
    let candidateID: String
    let decision: String
    let note: String
    let createdAt: String
    let left: JusticiaGroundedClaimDTO
    let right: JusticiaGroundedClaimDTO

    var id: String { recordID }

    enum CodingKeys: String, CodingKey {
        case recordID = "record_id"
        case matterID = "matter_id"
        case candidateID = "candidate_id"
        case decision, note
        case createdAt = "created_at"
        case left, right
    }
}
