# Desktop full-corpus persistence

The standalone macOS runtime owns a local, Matter-scoped legal corpus.  It does not
use Supabase, pgvector or cloud services to reopen a desktop Matter.

| Domain object | Desktop persistence | Protection / recovery |
| --- | --- | --- |
| Matter, deadlines, audit events | `matters.sqlite3` | AES-GCM encrypted record payloads. |
| Original PDF/DOCX/TXT bytes | `documents/<document-id>.jafarblob` | AES-GCM blob; atomic write/rename; authenticated with document ID and fingerprint. |
| Name, media type, fingerprint, extracted text | `corpus.sqlite3` document payload | AES-GCM encrypted payload. No external source path is retained. |
| OCR records and verification state | `corpus.sqlite3` document payload | AES-GCM encrypted; `ocr_unverified`, `text_layer_verified`, and `visually_verified` remain distinct. |
| Facts, conflicts and provenance | `corpus.sqlite3` document payload | AES-GCM encrypted; no automatic conflict reconciliation. |
| RAG chunks, citation metadata, optional embedding | `corpus.sqlite3` chunk payload | AES-GCM encrypted and Matter-scoped. |
| Vector index | None in beta | Retrieval deterministically rebuilds in memory from encrypted chunks; no cloud embedding call. |
| Logs, cache and temporary files | app-owned directories only | No durable document body or prompt cache. |

SQLite retains only opaque document/Matter identifiers, ordering timestamps, state and
the minimum foreign keys needed for Matter isolation.  Content names, fingerprints,
text, OCR, facts, provenance, chunks and embeddings are encrypted.  This does not
hide metadata such as record counts and timestamps.

## Ingestion and recovery

The explicit desktop import path parses in memory, creates an encrypted blob using a
fresh nonce, then atomically commits encrypted metadata and chunks.  A failure never
marks a document `READY`; a new blob is removed if its metadata transaction fails.
Startup removes orphaned encrypted blobs and stale encrypted temporary files.  A
missing blob, wrong key, unknown schema, corrupted blob, or tampered record fails
closed.  Derived retrieval is rebuilt locally from canonical encrypted chunks; it
never re-imports source data or sends it to cloud.

Documents are intentionally not deduplicated across Matters in beta.  This avoids a
shared blob becoming an authorization or provenance boundary.  Stable IDs and
fingerprints are retained inside encrypted metadata.  Explicit document deletion
requires approval and removes its chunk rows before its encrypted blob.

## Key lifecycle

The macOS Keychain retains the per-install master key.  Separate HKDF contexts derive
Matter and corpus keys.  If an existing database cannot be opened with that key,
JAFAR reports local storage unavailable and does not create a replacement database.
Future rotation must decrypt/verify every payload into a separately staged store,
atomically switch only after verification, and retain the old key until backup and
rollback checks succeed.
