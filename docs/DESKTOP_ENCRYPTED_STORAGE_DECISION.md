# Desktop encrypted storage decision

JAFAR 2.1 beta uses standard SQLite with WAL and full synchronous transactions for
durability.  Legal Matter and event payloads are encrypted separately with
AES-256-GCM from `cryptography`; record ID is authenticated additional data.  The
database retains only query metadata required for isolation and ordering (opaque ID
and timestamps).  A per-install 256-bit master key is stored in the macOS Keychain.
The sidecar receives it only as a child-only environment value, derives its storage
key with HKDF-SHA-256, and never writes it to disk, logs or command arguments.

SQLCipher was rejected for beta because it adds a native SQLite fork that must be
packaged, inspected and signed across PyInstaller/Hardened Runtime/notarization.
Plain SQLite was rejected because it leaks Matter text.  Encrypting each domain
payload keeps SQLite migration/transaction semantics and uses mature authenticated
cryptography without a new database engine.

Threat coverage: raw DB copies and WAL data do not expose Matter payload text; a
wrong key or altered payload fails closed with authenticated-integrity failure;
single-writer locking prevents concurrent local app corruption.  This complements,
but does not replace, macOS account controls, FileVault and secure backups.

Limitations: IDs and timestamps remain visible metadata.  Application-controlled
document/RAG persistence is not yet enabled for desktop beta, so no plaintext source
document or RAG store is created by this repository.  It must use the same encrypted
payload boundary before being enabled.  The key is passed only to the directly
spawned sidecar and is not inherited from the user's shell, but same-user privileged
process inspection remains a macOS threat-model boundary; a future authenticated IPC
key handoff can further reduce that in-memory exposure.  The sidecar consumes the raw
Keychain value exactly once at bootstrap, derives separate Matter/corpus keys, and
removes the raw environment entry before importing its ASGI application. Python's
best-effort temporary-buffer clearing is not a guarantee of memory zeroization.
