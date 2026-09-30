# Desktop data classification

| Category | Desktop beta status | Storage / protection |
| --- | --- | --- |
| Matters, deadlines, events | Required | Encrypted SQLite payloads in Application Support; Keychain-derived key. |
| Original documents | Required after explicit desktop import | AES-GCM encrypted blobs in `Application Support/JAFAR/documents`; no external path retained. |
| Extracted text, OCR, facts, provenance | Required after explicit desktop import | AES-GCM encrypted corpus records; verification states remain distinct. |
| RAG chunks and optional embeddings | Required after explicit desktop import | AES-GCM encrypted corpus records; local deterministic retrieval rebuilds in memory. |
| OAuth, OpenAI, Telegram, Supabase | Optional / disabled at first run | No desktop config file; secrets belong in Keychain if a future opt-in is implemented. |
| Local AI settings | Non-sensitive | Runtime defaults only; Ollama is loopback. |
| Logs / diagnostics | Required metadata only | No prompt, document body, Matter fields, token or key. |
| Cache / temporary data | Minimal | App-owned directories, mode `0700`; encrypted temporary blob writes are removed after atomic rename or next launch. |
| Licensing | Stub only | Never authorizes Matters, IPC or approval gates. |

Retention is user-controlled and no cloud backup, Google Drive or iCloud upload is
started automatically.  Matter deletion remains a future explicit approval flow;
the beta makes no claim of secure deletion on APFS/SSD.
