# Desktop backup and recovery

The complete local corpus is `matters.sqlite3`, `corpus.sqlite3`, their WAL/SHM
sidecars, and `documents/` encrypted blobs.  Restoring only the Matter database is
not a complete backup.  These application payloads are encrypted, but restoration
also requires the original macOS Keychain item.  A raw copy is therefore suitable
only for same-user/same-Keychain recovery and must be made while JAFAR is closed.
Do not upload it automatically.

Portable encrypted export is deferred: it needs an explicit user passphrase, a
memory-hard KDF, authenticated archive format and restore UX.  Restore must first
validate schema version and authenticated payloads; a failure must preserve the
existing database and never reset/delete Matters.
