# JAFAR 2.1 — Encrypted local draft history (beta)

## User goal

A lawyer can start a document, save it locally, close JAFAR, reopen the same
Matter and continue editing without starting over. After the first explicit
save, subsequent edits are auto-saved with a short debounce. The editor
does not silently switch Matters or overwrite a newer revision.

## Storage

- The standalone macOS backend keeps a separate local database
  at Application Support/JAFAR/drafts.sqlite3. It is not a Supabase table.
- A subkey is derived from the Keychain-provided desktop corpus key with
  a dedicated HKDF context. The raw master key is not stored with the drafts.
- Each revision is an AES-256-GCM encrypted payload authenticated to
  Matter ID, draft ID and revision number (AEAD associated data).
- Recipient, author, arguments, requested action and source-document IDs
  are encrypted. SQLite stores only opaque identifiers, timestamps and
  revision numbers. Counts/timestamps are observable as local metadata.
- Revisions are append-only. The revision expected by the caller must match
  the current revision. Conflicting saves get HTTP 409 and preserve content.
- A wrong key or corrupt ciphertext fails closed. The backend does not
  overwrite or regenerate an existing database without its key check.
- An explicit restore makes a new revision; it never deletes prior versions.
- There is a 200-revision cap per document to bound uncontrolled growth.
- Export remains an explicit operation through the existing Word endpoint,
  which **rechecks source integrity and required fields**.

## UI

In "Шаблоны" the document editor shows a panel:

- "Сохранить черновик" creates the first record. Afterward edits use an
  approximately 1.2-second debounce.
- "Открыть сохранённый" lists saved drafts only for the current Matter.
- The revision number and recent history are visible.
- Selecting an old revision shows its user-authored position. Restoring it
  requires explicit confirmation and writes a new revision.
- A revision collision produces a warning; a stale editor does not overwrite
  the more recent version.
- Switching Matters resets the visible editor and local draft context.

## API

Only available when JAFAR desktop mode creates the encrypted store, behind
the per-launch loopback bearer:

- GET/POST /v1/matters/{matter_id}/drafts
- GET/PUT /v1/matters/{matter_id}/drafts/{draft_id}
- GET /v1/matters/{matter_id}/drafts/{draft_id}/revisions
- GET /v1/matters/{matter_id}/drafts/{draft_id}/revisions/{revision}
- POST /v1/matters/{matter_id}/drafts/{draft_id}/restore

Restore requests must contain approved=true, source_revision and the
expected current revision. All write endpoints return the saved version.
The existing /drafts/preview, /drafts/suggest and /drafts/export keep their
current local-only behavior. No automatic signing, filing or email.

## Limitations

There is no backup, account synchronisation, conflict merge, encrypted
portable export, or regulatory retention policy yet. Local storage encryption
does not substitute for FileVault, physical-device protections, data governance
or legal professional secrecy obligations. The history does not establish
the substantive correctness of a legal argument.

The beta uses synthetic fixtures only. Run full Python CI, Apple iOS/macOS,
Ollama and macOS packaging checks; on a clean Apple Silicon Mac verify
save/reopen, force quit/restart, changed Matter isolation, concurrent editing
conflict, restore and source revalidation before real-client use.
