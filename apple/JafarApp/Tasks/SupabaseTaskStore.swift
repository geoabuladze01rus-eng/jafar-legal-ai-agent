import Foundation
import Supabase

struct SupabaseTaskStore {
    let client: SupabaseClient

    struct CaseTaskRow: Codable, Sendable {
        let id: UUID
        let caseId: UUID
        let task: String
        let dueDate: Date?
        let status: String
        let priority: String

        enum CodingKeys: String, CodingKey {
            case id
            case caseId = "case_id"
            case task
            case dueDate = "due_date"
            case status
            case priority
        }
    }

    func createTask(caseId: UUID, task: String, dueDate: Date? = nil, priority: String = "high") async throws -> CaseTaskRow {
        struct Insert: Encodable {
            let caseId: UUID
            let task: String
            let dueDate: Date?
            let priority: String
            enum CodingKeys: String, CodingKey {
                case caseId = "case_id"
                case task
                case dueDate = "due_date"
                case priority
            }
        }

        return try await client
            .from("case_tasks")
            .insert(Insert(caseId: caseId, task: task, dueDate: dueDate, priority: priority))
            .select()
            .single()
            .execute()
            .value
    }
}
