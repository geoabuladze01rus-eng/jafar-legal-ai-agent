import Foundation
import Security

extension JafarAPIError: LocalizedError {
    var errorDescription: String? {
        switch self {
        case .invalidResponse:
            return "Backend вернул некорректный ответ."
        case let .httpStatus(status):
            if status == 401 {
                return "Backend отклонил API token."
            }
            return "Backend ответил HTTP \(status)."
        case let .keychain(status):
            if let message = SecCopyErrorMessageString(status, nil) as String? {
                return "Keychain: \(message)"
            }
            return "Ошибка Keychain (\(status))."
        }
    }
}
