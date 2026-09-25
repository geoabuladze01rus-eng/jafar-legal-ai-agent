# Ollama security boundary

For confidential desktop operation, JAFAR validates that its configured Ollama URL is
loopback-only (`127.0.0.1`, `localhost`, or `::1`) and sends no automatic cloud
fallback.  The default local model is `qwen3:4b`.  JAFAR rejects remote, LAN and
wildcard endpoints for confidential Ollama processing.

Ollama is a separately installed, user-administered local dependency outside JAFAR's
trusted application implementation boundary.  JAFAR does not control Ollama's
installation security, logs, storage/cache, model implementation, telemetry settings,
or administrator modifications.  A loopback check establishes destination locality;
it does not cryptographically identify the service on that port.  A substituted local
service, compromised OS, or same-user privileged process is part of the local-host
threat boundary, not a guarantee provided by JAFAR.
