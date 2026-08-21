import Foundation
import Combine

enum JafarNotificationKind: String, Sendable {
    case deadline
    case overdue
    case criticalRisk
    case newLegalMail
    case approvalRequired
}

struct JafarNotificationItem: Identifiable, Sendable {
    let id: String
    let kind: JafarNotificationKind
    let title: String
    let body: String
    let createdAt: Date
    let priority: Int
    let requiresApproval: Bool
}

@MainActor
final class JafarNotificationCenter: ObservableObject {
    @Published private(set) var items: [JafarNotificationItem] = []

    func add(_ item: JafarNotificationItem) {
        items.removeAll { $0.id == item.id }
        items.append(item)
        items.sort { $0.priority > $1.priority }
    }

    func remove(id: String) {
        items.removeAll { $0.id == id }
    }

    func clearResolved() {
        items.removeAll { !$0.requiresApproval }
    }
}
