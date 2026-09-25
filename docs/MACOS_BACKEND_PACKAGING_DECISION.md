# macOS backend packaging decision

JAFAR 2.1.0-beta.1 packages the Python legal backend as an Apple Silicon
**PyInstaller one-folder sidecar** at `JAFAR.app/Contents/Resources/Helpers/JafarBackend/`.
The Swift application launches the contained `JafarBackend` executable directly;
the customer never needs Git, a source checkout, a virtual environment, Terminal,
or a system Python installation.

## Why one-folder PyInstaller

The current runtime is Python 3.12, FastAPI/Uvicorn, Pydantic, HTTPX, cryptography,
and optional connectors.  One-folder packaging keeps the interpreter, native wheels,
dynamic libraries and certificates inspectable beside a small executable.  That is
materially easier to audit, diagnose, update atomically and sign inside-out than a
compressed one-file bootstrap.  It has an intentional size cost.

## Alternatives considered

| Candidate | Decision | Reason |
| --- | --- | --- |
| PyInstaller one-file | Rejected | Slow unpack-on-launch behaviour and an opaque temporary runtime are poor fits for confidential case work. |
| Nuitka | Deferred | Promising, but needs native-extension compatibility validation across the full optional document stack before it can replace a proven frozen-runtime baseline. |
| python-build-standalone / embedded CPython | Deferred | More explicit, but requires a substantial custom dependency and bootstrap layer now. |
| Briefcase | Rejected for this sidecar | It targets full Python applications; it does not reduce the existing Swift-app + FastAPI lifecycle boundary. |

## Runtime boundary

The sidecar receives a dedicated `JAFAR_RUNTIME_MODE=desktop`, binds only to
`127.0.0.1`, needs a 32-byte per-launch IPC bearer token, has cloud fallback and
production sending disabled, and gets no inherited developer or deployment secrets.
It uses application-owned paths under `~/Library/Application Support/JAFAR`,
`~/Library/Logs/JAFAR` and `~/Library/Caches/JAFAR`; mutable data is never written
inside the app bundle.

The desktop baseline intentionally uses in-memory matter storage until a separate,
audited local encrypted persistence layer is introduced.  Supabase, OAuth,
Telegram and OpenAI are optional integrations and do not start or become required
for launch.  Ollama remains a separate local loopback service.

The artifact scanner rejects credentials, keys, `.env` and repository metadata.  The
only permitted PEM is certifi's public `cacert.pem`, required for outbound TLS
verification; it is a CA trust bundle, not private signing material.

## Signing and updates

The one-folder directory is nested executable code.  Future Developer ID signing
must sign every nested dylib/framework/native extension and `JafarBackend` first,
then the main application; `codesign --deep` is not a replacement for that order.
An updater must replace the whole signed app bundle, including the sidecar, while
all mutable state remains outside it.

## Version mapping

The Python package uses the PEP 440 version `2.1.0b1`; the macOS marketing version
is the Apple-valid numeric `2.1.0` with build number `1`; the artifact name shown to
beta users is `JAFAR-2.1.0-beta.1-macos-arm64.dmg`.  No tag or public release is
created by this branch.
