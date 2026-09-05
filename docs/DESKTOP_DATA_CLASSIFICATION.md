# Desktop data classification

| Category | Desktop beta status | Storage / protection |
| --- | --- | --- |
| Matters, deadlines, events | Required | Encrypted SQLite payloads in Application Support; Keychain-derived key. |
| Documents, extracted text, OCR, RAG, embeddings, facts, provenance | Not persisted by desktop beta | Must use the encrypted payload boundary before enablement. |
| OAuth, OpenAI, Telegram, Supabase | Optional / disabled at first run | No desktop config file; secrets belong in Keychain if a future opt-in is implemented. |
| Local AI settings | Non-sensitive | Runtime defaults only; Ollama is loopback. |
| Logs / diagnostics | Required metadata only | No prompt, document body, Matter fields, token or key. |
| Cache / temporary data | Minimal | App-owned directories, mode `0700`; no durable legal content. |
| Licensing | Stub only | Never authorizes Matters, IPC or approval gates. |

Retention is user-controlled and no cloud backup, Google Drive or iCloud upload is
started automatically.  Matter deletion remains a future explicit approval flow;
the beta makes no claim of secure deletion on APFS/SSD.
