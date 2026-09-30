import Foundation

enum JusticiaBetaDiagnosticsSnapshot {
    static var appVersion: String {
        Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "—"
    }

    static var buildNumber: String {
        Bundle.main.object(forInfoDictionaryKey: "CFBundleVersion") as? String ?? "—"
    }

    static var systemVersion: String {
        ProcessInfo.processInfo.operatingSystemVersionString
    }

    static var architecture: String {
        #if arch(arm64)
        return "arm64"
        #elseif arch(x86_64)
        return "x86_64"
        #else
        return "unknown"
        #endif
    }

    static var report: String {
        [
            "Юстиция — beta diagnostics",
            "Version: \(appVersion)",
            "Build: \(buildNumber)",
            "OS: \(systemVersion)",
            "Architecture: \(architecture)",
            "Data note: no matter/document/transcript contents included"
        ].joined(separator: "\n")
    }
}
