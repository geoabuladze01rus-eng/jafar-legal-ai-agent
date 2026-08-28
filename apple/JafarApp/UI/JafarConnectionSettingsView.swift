import SwiftUI

struct JafarConnectionSettingsView: View {
    @Environment(\.dismiss) private var dismiss

    @State private var baseURL = JafarAPIConfiguration.baseURLString
    @State private var token = JafarCredentialStore.readToken() ?? ""
    @State private var errorMessage: String?

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
                }

                Section("Безопасность") {
                    Label("API token хранится в Keychain", systemImage: "key.fill")
                    Label("Юридические данные не записываются в настройки", systemImage: "lock.shield.fill")
                    Label("Пустой адрес переводит приложение в локальный режим", systemImage: "laptopcomputer")
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

    private func save() {
        if let validationError {
            errorMessage = validationError
            return
        }
        do {
            try JafarAPIConfiguration.save(baseURLString: baseURL, token: token)
            errorMessage = nil
            onSaved()
            dismiss()
        } catch {
            errorMessage = "Не удалось сохранить защищённые настройки: \(error.localizedDescription)"
        }
    }

    private func disableRemote() {
        do {
            try JafarAPIConfiguration.disableRemoteMode()
            baseURL = ""
            token = ""
            errorMessage = nil
            onSaved()
            dismiss()
        } catch {
            errorMessage = "Не удалось очистить API token: \(error.localizedDescription)"
        }
    }
}
