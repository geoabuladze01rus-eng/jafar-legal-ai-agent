# JAFAR macOS beta acceptance checklist

Run this checklist on a Mac without the repository checked out.

1. Mount the unsigned beta DMG and copy `JAFAR.app` to Applications.
2. Confirm no Git, Python, Codex, repository, `.env`, or source-tree path is required to launch the client.
3. Launch the app and verify microphone/speech permission prompts are shown only when voice capture is requested.
4. Verify the macOS Local AI panel reports one of: `LOCAL AI READY`, `OLLAMA NOT INSTALLED`, `OLLAMA NOT RUNNING`, `QWEN3:4B MODEL MISSING`, or `LOCAL AI CONNECTION ERROR`.
5. With Ollama running on loopback and `qwen3:4b` installed, verify the panel reports `LOCAL AI READY`.
6. Run a synthetic local command. Confirm no network destination other than the configured loopback endpoint is used for confidential local work.
7. Verify the app remains usable when Ollama is absent and reports guidance instead of silently using cloud AI.
8. Quit and relaunch. Confirm state does not expose developer paths or credentials.
9. Inspect the installed bundle for `.env`, `.git`, tests, credentials, tokens, private keys, case files, and temporary logs.
10. Record macOS version, app version, bundle hash, Ollama version/model, and any permission or launch failures.

This checklist is a beta gate, not evidence of notarized commercial distribution.
