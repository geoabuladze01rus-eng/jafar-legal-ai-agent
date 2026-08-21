import SwiftUI

struct DeadlineConfirmationView: View {
    let proposal: DeadlineProposalViewModel
    let onConfirm: (Date) -> Void
    let onReject: () -> Void

    @State private var dueDate: Date

    init(proposal: DeadlineProposalViewModel, onConfirm: @escaping (Date) -> Void, onReject: @escaping () -> Void) {
        self.proposal = proposal
        self.onConfirm = onConfirm
        self.onReject = onReject
        _dueDate = State(initialValue: proposal.dueDate)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            Label("Найден возможный срок", systemImage: "calendar.badge.exclamationmark")
                .font(.title2.bold())

            Text(proposal.basis)
                .foregroundStyle(.secondary)

            DatePicker("Дата", selection: $dueDate, displayedComponents: [.date])

            LabeledContent("Уверенность", value: "\(Int(proposal.confidence * 100))%")

            HStack {
                Button("Отклонить", role: .destructive, action: onReject)
                Spacer()
                Button("Подтвердить") { onConfirm(dueDate) }
                    .buttonStyle(.borderedProminent)
            }
        }
        .padding()
    }
}

struct DeadlineProposalViewModel {
    let sourceId: String
    let dueDate: Date
    let basis: String
    let confidence: Double
}
