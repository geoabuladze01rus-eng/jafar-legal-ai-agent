import SwiftUI

struct JafarDashboardView: View {
    let snapshot: DashboardSnapshot

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    Text("Добрый день, сэр")
                        .font(.largeTitle.bold())

                    Text("Что требует внимания сейчас")
                        .foregroundStyle(.secondary)

                    SectionCard(title: "Критические сроки", systemImage: "exclamationmark.triangle.fill") {
                        if snapshot.criticalDeadlines.isEmpty {
                            EmptyRow(text: "Критических сроков нет")
                        } else {
                            ForEach(Array(snapshot.criticalDeadlines.enumerated()), id: \.offset) { _, item in
                                VStack(alignment: .leading, spacing: 4) {
                                    Text(item.title).font(.headline)
                                    Text(item.due_at, style: .date)
                                        .font(.subheadline)
                                        .foregroundStyle(.secondary)
                                    Text(item.level.uppercased())
                                        .font(.caption.bold())
                                }
                            }
                        }
                    }

                    SectionCard(title: "Задачи", systemImage: "checklist") {
                        if snapshot.tasks.isEmpty {
                            EmptyRow(text: "Открытых задач нет")
                        } else {
                            ForEach(Array(snapshot.tasks.enumerated()), id: \.offset) { _, task in
                                VStack(alignment: .leading, spacing: 4) {
                                    Text(task.title).font(.headline)
                                    Text(task.status).font(.caption)
                                }
                            }
                        }
                    }

                    SectionCard(title: "Почта", systemImage: "envelope.fill") {
                        if snapshot.inbox.isEmpty {
                            EmptyRow(text: "Новых юридически значимых писем нет")
                        } else {
                            ForEach(Array(snapshot.inbox.enumerated()), id: \.offset) { _, item in
                                VStack(alignment: .leading, spacing: 4) {
                                    Text(item.subject).font(.headline)
                                    Text(item.sender).font(.subheadline)
                                    Text(item.category).font(.caption)
                                }
                            }
                        }
                    }

                    SectionCard(title: "Последние события", systemImage: "clock.arrow.circlepath") {
                        ForEach(snapshot.recent_events, id: \.self) { event in
                            Text(event)
                        }
                    }
                }
                .padding()
            }
            .navigationTitle("Джафар")
        }
    }
}

private struct SectionCard<Content: View>: View {
    let title: String
    let systemImage: String
    @ViewBuilder let content: Content

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Label(title, systemImage: systemImage)
                .font(.headline)
            content
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding()
        .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 18))
    }
}

private struct EmptyRow: View {
    let text: String
    var body: some View {
        Text(text).foregroundStyle(.secondary)
    }
}
