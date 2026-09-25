# JAFAR beta troubleshooting

The user-safe diagnostic report may show app/backend version, local engine state,
local storage state, Ollama reachability and qwen3:4b state.  It must not contain
Matter text, prompts, keys, bearer tokens, OAuth credentials or database payloads.

`LOCAL STORAGE UNAVAILABLE` means Keychain or encrypted database initialization
failed.  JAFAR must remain unavailable for Matter writes; it must not create an
unencrypted replacement database.  `LOCAL AI` status is independent: users can
install/start Ollama and explicitly obtain qwen3:4b, but JAFAR must not silently
substitute cloud processing.
