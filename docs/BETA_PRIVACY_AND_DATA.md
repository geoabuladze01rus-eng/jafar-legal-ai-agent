# JAFAR beta privacy and data

JAFAR stores Matter data and explicitly imported legal documents locally in encrypted
application-managed storage.  Original document bytes, extracted text, OCR records,
facts, provenance, RAG chunks and optional embeddings use authenticated encryption at
rest.  The default AI path is local Ollama.  Cloud AI is not enabled automatically
for confidential work.  Optional Google, cloud AI and messaging integrations do not
start merely because the beta launches.

JAFAR sends local AI requests only to the configured loopback Ollama service. Ollama
is separately installed and administered on the Mac; its own storage, logs, model
behavior and machine-level configuration are outside JAFAR's control.

JAFAR does not automatically upload Matters, documents, prompts or backups.  Safe
diagnostics contain only component state and versions, never document content or
credentials.  This beta does not yet provide portable encrypted export or a cloud
backup service; users should treat their Mac account, FileVault and Keychain as part
of the operating security boundary.
