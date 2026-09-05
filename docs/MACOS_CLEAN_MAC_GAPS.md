# Clean-Mac delivery gap analysis

| Area | Status | Exact next action |
| --- | --- | --- |
| SwiftUI client bundle | PARTIAL | Keep the arm64 Release/DMG path reproducible and add launch telemetry-free acceptance checks. |
| Local Ollama detection | READY | Keep loopback-only model/service diagnostics and add UI copy review during beta. |
| Python legal backend | BLOCKED (P0) | Package and supervise an arm64 local backend sidecar, or explicitly require a separately installed local service. |
| Developer ID signing | BLOCKED (P1) | Obtain a Developer ID Application identity and define nested-component signing order. |
| Notarization | BLOCKED (P1) | Store a `notarytool` Keychain profile and run submit/wait/staple/assessment. |
| DMG foundation | READY (unsigned) | Use the script output only for internal beta validation until signed. |
| Licensing | PARTIAL | Review and approve the separate licensing boundary before implementation. |
| Auto-update | PARTIAL | Select an update framework/feed owner and provision update signing keys. |
| Clean-Mac beta proof | PARTIAL | Execute `docs/MACOS_BETA_ACCEPTANCE.md` on a machine without the repository. |
