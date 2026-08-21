import SwiftUI

struct MatterDetailView: View {
    let matter: Matter
    let events: [MatterTimelineEvent]
    let tasks: [Task]

    var body: some View {
        List {
            Section("Дело") {
                LabeledContent("Название", value: matter.title)
                LabeledContent("Тип", value: matter.matter_type)
                LabeledContent("Статус", value: matter.status)
                if let number = matter.case_number {
                    LabeledContent("Номер", value: number)
                }
            }

            Section("Задачи") {
                if tasks.isEmpty {
                    Text("Задач нет").foregroundStyle(.secondary)
                } else {
                    ForEach(Array(tasks.enumerated()), id: \.offset) { _, task in
                        VStack(alignment: .leading) {
                            Text(task.title).font(.headline)
                            Text(task.status.rawValue).font(.caption)
                            if let due = task.due_at {
                                Text(due, style: .date).font(.caption2)
                            }
                        }
                    }
                }
            }

            Section("Хронология") {
                if events.isEmpty {
                    Text("Событий пока нет").foregroundStyle(.secondary)
                } else {
                    ForEach(events, id: \.event_id) { event in
                        VStack(alignment: .leading, spacing: 4) {
                            Text(event.title).font(.headline)
                            Text(event.event_type.rawValue).font(.caption)
                            Text(event.occurred_at, style: .date).font(.caption2)
                            if let summary = event.summary {
                                Text(summary).foregroundStyle(.secondary)
                            }
                        }
                    }
                }
            }
        }
        .navigationTitle("Дело")
    }
}
