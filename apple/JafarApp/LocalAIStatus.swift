#if os(macOS)
import SwiftUI

private struct OllamaTagsResponse: Decodable {
    let models: [OllamaModel]
}

private struct OllamaModel: Decodable {
    let name: String?
    let model: String?
}

private enum LocalAIState: Equatable {
    case checking
    case ready
    case notInstalled
    case notRunning
    case modelMissing
    case connectionError

    var title: String {
        switch self {
        case .checking: "ПРОВЕРЯЕМ LOCAL AI"
        case .ready: "LOCAL AI READY"
        case .notInstalled: "OLLAMA NOT INSTALLED"
        case .notRunning: "OLLAMA NOT RUNNING"
        case .modelMissing: "QWEN3:4B MODEL MISSING"
        case .connectionError: "LOCAL AI CONNECTION ERROR"
        }
    }

    var color: Color {
        switch self {
        case .ready: .green
        case .checking: .secondary
        default: .orange
        }
    }
}

struct LocalAIStatusView: View {
    @State private var state: LocalAIState = .checking
    @State private var detail = "Проверяем локальный Ollama без отправки данных в облако…"

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Label(state.title, systemImage: state == .ready ? "checkmark.shield" : "waveform.path.ecg")
                .font(.headline)
                .foregroundStyle(state.color)
            Text(detail)
                .font(.caption)
                .foregroundStyle(.secondary)
            if state != .ready {
                Text("Установите Ollama, запустите его и установите модель qwen3:4b. JAFAR не отправляет конфиденциальные данные в облако автоматически.")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
            }
            Button("Проверить снова") {
                Task { await refresh() }
            }
            .buttonStyle(.bordered)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(12)
        .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 10))
        .task { await refresh() }
    }

    private func refresh() async {
        state = .checking
        detail = "Проверяем только loopback endpoint 127.0.0.1:11434…"
        guard let url = URL(string: "http://127.0.0.1:11434/api/tags") else {
            state = .connectionError
            detail = "Не удалось подготовить локальную проверку."
            return
        }

        do {
            let (data, response) = try await URLSession.shared.data(from: url)
            guard let httpResponse = response as? HTTPURLResponse else {
                state = .connectionError
                detail = "Ollama вернул некорректный ответ."
                return
            }
            guard (200...299).contains(httpResponse.statusCode) else {
                state = httpResponse.statusCode == 404 ? .notInstalled : .notRunning
                detail = "Локальный endpoint ответил HTTP \(httpResponse.statusCode)."
                return
            }
            let payload = try JSONDecoder().decode(OllamaTagsResponse.self, from: data)
            let hasModel = payload.models.contains { ($0.name ?? $0.model) == "qwen3:4b" }
            state = hasModel ? .ready : .modelMissing
            detail = hasModel ? "Ollama доступен локально; qwen3:4b готова." : "Ollama доступен, но qwen3:4b не найдена."
        } catch let error as URLError where error.code == .cannotFindHost || error.code == .cannotConnectToHost {
            state = .notRunning
            detail = "Ollama не запущен на локальном компьютере."
        } catch {
            state = .connectionError
            detail = "Не удалось проверить локальный Ollama endpoint."
        }
    }
}
#endif
