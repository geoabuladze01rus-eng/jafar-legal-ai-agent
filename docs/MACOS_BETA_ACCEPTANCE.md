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
# Standalone backend acceptance upgrade (JAFAR 2.1 beta)

Run this synthetic acceptance on a clean compatible Apple Silicon Mac before
distribution.  It is deliberately different from later Gatekeeper acceptance.

1. Confirm no source checkout, Git, virtualenv, system Python or Terminal command is
   required to open `JAFAR.app` from the DMG.
2. Launch the Swift app and confirm it changes from **STARTING JAFAR** to
   **LOCAL ENGINE READY**.  The bundled sidecar must answer its loopback health check.
3. Confirm the local Ollama status separately reports the qwen3:4b state.  Do not
   configure cloud fallback or send real legal material.
4. Use synthetic data to make a local Matter operation.  Confirm an unauthenticated
   request to the sidecar's `/v1/*` endpoint is rejected and that the ephemeral IPC
   token is neither stored nor shown in diagnostics.
5. Quit, relaunch three times, and verify no orphan sidecar or fixed-port leak
   remains.  Verify `~/Library/Application Support/JAFAR`, `~/Library/Logs/JAFAR`
   and `~/Library/Caches/JAFAR` are the only mutable runtime locations.
6. Inspect the DMG/app for `.env`, `.git`, developer paths, credentials, real case
   documents and test fixtures.  None may be present.

This is a **pre-signing local acceptance**.  A separate post-notarization Gatekeeper
acceptance is required after a Developer ID Application certificate and a Keychain
notarytool profile are available.
