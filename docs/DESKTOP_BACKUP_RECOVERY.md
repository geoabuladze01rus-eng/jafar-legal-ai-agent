# Desktop backup and recovery

The local SQLite database and its WAL/SHM sidecars are encrypted at the application
payload layer, but restoring them also requires the original macOS Keychain item.
For that reason a raw copy is suitable only for same-user/same-Keychain recovery and
must be made while JAFAR is closed.  Do not upload it automatically.

Portable encrypted export is deferred: it needs an explicit user passphrase, a
memory-hard KDF, authenticated archive format and restore UX.  Restore must first
validate schema version and authenticated payloads; a failure must preserve the
existing database and never reset/delete Matters.
