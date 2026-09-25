# JAFAR 2.1 canonical reconciliation

This branch is an integration-only import of the current Telegram/Supabase production source line into the JAFAR 2.1 canonical reconciliation flow.

Source Telegram/Supabase head: `2faf033df8596a0391f7e6062065709cbbf35308`.
Canonical desktop/security base was created from: `4df9eb40279216c917912fa065a007fdf628d561`.

Safety constraints:
- do not merge to `main` from this branch;
- do not deploy production from this branch;
- do not sign, notarize, tag, release, or rewrite history;
- require the full Python, Apple, Ollama, macOS packaging, security, provenance, RAG and Telegram gates on the merged PR result before accepting this import;
- keep production deployment parity review separate from source reconciliation.

The purpose of this branch is only to create a fresh pull-request event so GitHub Actions validate the actual reconciliation result against `integration/jafar-2.1-canonical`.
