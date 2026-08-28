import SwiftUI

struct JafarConnectionSettingsView: View {
    @Environment(\.dismiss) private var dismiss

    @State private var baseURL = JafarAPIConfiguration.baseURLString
    @State private var token = JafarCredentialStore.readToken() ?? ""
    @State private var errorMessage: String?
    @State private var successMessage: String?
    @State private var isTesting = false

    let onSaved: () -> Void

    var body: some View {
        NavigationStack {
            Form {
                Section("Подключение") {
                    TextField("https://jafar.example.ru", text: $baseURL)
                        .textFieldStyle(.roundedBorder)

                    SecureField("API token", text: $token)
                        .textFieldStyle(.roundedBorder)

                    Text(
                        "Для рабочего сервера используется HTTPS. HTTP разрешён только "
                            + "для localhost при локальной разработке."
                    )
                    .font(.caption)
                    .foregroundStyle(.secondary)

                    Button {
                        Task { await testConnection() }
                    } label: {
                        if isTesting {
                            HStack(spacing: 8) {
                                ProgressView()
                                    .controlSize(.small)
                                Text("Проверяю подключение…")
                            }
                        } else {
                            Label("Проверить подключение", systemImage: "network")
                        }
                    }
                    .disabled(isTesting || validationError != nil || normalizedURL == nil)
                }

                Section("Безопасность") {
                    Label("API token хранится в Keychain", systemImage: "key.fill")
                    Label(
                        "Юридические данные не записываются в настройки",
                        systemImage: "lock.shield.fill"
                    )
                    Label(
                        "Пустой адрес переводит приложение в локальный режим",
                        systemImage: "laptopcomputer"
                    )
                }

                if let successMessage {
                    Section {
                        Label(successMessage, systemImage: "checkmark.circle.fill")
                            .foregroundStyle(.green)
                    }
                }

                if let errorMessage {
                    Section {
                        Label(errorMessage, systemImage: "exclamationmark.triangle.fill")
                            .foregroundStyle(.red)
                    }
                }

                Section {
                    Button("Сохранить подключение") {
                        save()
                    }
                    .disabled(validationError != nil)

                    Button("Перейти в локальный режим", role: .destructive) {
                        disableRemote()
                    }
                }
            }
            .navigationTitle("Подключение Джафара")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Закрыть") {
                        dismiss()
                    }
                }
            }
        }
    }

    private var normalizedURL: URL? {
        let value = baseURL.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !value.isEmpty else { return nil }
        return URL(string: value)
    }

    private var validationError: String? {
        let value = baseURL.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !value.isEmpty else { return nil }
        guard let url = URL(string: value),
              let scheme = url.scheme?.lowercased(),
              let host = url.host?.lowercased(),
              !host.isEmpty else {
            return "Укажите корректный адрес backend."
        }
        if url.user != nil || url.password != nil {
            return "Логин и пароль нельзя помещать в URL. Используйте API token."
        }
        if scheme == "https" {
            return nil
        }
        let localHosts = ["localhost", "127.0.0.1", "::1"]
        if scheme == "http" && localHosts.contains(host) {
            return nil
        }
        return "Рабочий backend должен использовать HTTPS."
    }

    @MainActor
    private func testConnection() async {
        guard validationError == nil, let url = normalizedURL else { return }
        isTesting = true
        errorMessage = nil
        successMessage = nil
        defer { isTesting = false }

        do {
            let snapshot = try await RemoteDashboardClient(
                endpoint: url.appendingPathComponent("v1/dashboard"),
                authorizationToken: token.trimmingCharacters(in: .whitespacesAndNewlines)
            ).fetchDashboard()
            successMessage = "Backend отвечает. Активных дел: \(snapshot.activeMatters)."
        } catch {
            errorMessage = "Проверка подключения не пройдена: \(error.localizedDescription)"
        }
    }

    private func save() {
        if let validationError {
            errorMessage = validationError
            successMessage = nil
            return
        }
        do {
            try JafarAPIConfiguration.save(baseURLString: baseURL, token: token)
            errorMessage = nil
            onSaved()
            dismiss()
        } catch {
            successMessage = nil
            errorMessage = "Не удалось сохранить защищённые настройки: \(error.localizedDescription)"
        }
    }

    private func disableRemote() {
        do {
            try JafarAPIConfiguration.disableRemoteMode()
            baseURL = ""
            token = ""
            errorMessage = nil
            successMessage = nil
            onSaved()
            dismiss()
        } catch {
            successMessage = nil
            errorMessage = "Не удалось очистить API token: \(error.localizedDescription)"
        }
    }
}
