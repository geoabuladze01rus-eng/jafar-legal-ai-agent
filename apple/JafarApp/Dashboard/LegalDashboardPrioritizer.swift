import Foundation

struct LegalDashboardPrioritizer {
    func prioritize(_ items: [LegalDashboardItem], now: Date = Date()) -> [LegalDashboardItem] {
        items.sorted { lhs, rhs in
            let left = priority(lhs, now: now)
            let right = priority(rhs, now: now)
            if left != right { return left > right }
            if let l = lhs.dueAt, let r = rhs.dueAt, l != r { return l < r }
            return lhs.title.localizedCaseInsensitiveCompare(rhs.title) == .orderedAscending
        }
    }

    private func priority(_ item: LegalDashboardItem, now: Date) -> Int {
        var score = 0
        switch item.kind {
        case .risk: score += 80
        case .deadline: score += 70
        case .task: score += 40
        }
        if item.requiresApproval { score += 15 }
        if let dueAt = item.dueAt {
            let hours = dueAt.timeIntervalSince(now) / 3600
            if hours <= 24 { score += 40 }
            else if hours <= 72 { score += 25 }
            else if hours <= 168 { score += 10 }
            if hours < 0 { score += 60 }
        }
        score += Int(item.confidence * 10)
        return score
    }
}
