# macOS commercial packaging foundation

## Current application architecture

The XcodeGen project defines `JafarApp_macOS` and `JafarApp_iOS`, bundle identifier `ru.jafar.legal-ai`, Swift 5.10, and minimum macOS 14.0.  The macOS target launches an embedded arm64 Python sidecar from `Contents/Resources/Helpers/JafarBackend/`, waits for a loopback health response, and uses a per-launch bearer token for `/v1/*` calls.  It does not inherit developer, cloud, OAuth, Supabase or Telegram credentials.  The backend binds only `127.0.0.1`; Ollama remains a separately managed local loopback service.

## Reproducible local artifact

On an Apple Silicon Mac with Xcode, XcodeGen, and `hdiutil` installed:

```bash
./scripts/build_macos_release.sh
```

The script builds a Python 3.12 arm64 PyInstaller one-folder sidecar, generates the
project, builds Release arm64 with signing disabled, embeds the sidecar, validates
metadata and privacy keys, rejects credentials and local checkout/developer-home
paths, creates an Applications-link DMG, mounts and unmounts it, and writes a
SHA-256 sidecar. Output is under `dist/`, which is ignored and must never be
committed or attached to the stable `v2.0.0` release.

The current output is explicitly an unsigned beta/local artifact. It is not a commercial distribution.

## Signing and notarization

`ENABLE_HARDENED_RUNTIME=YES` is set in the generated target settings. No entitlements or broad exceptions are currently required. `scripts/notarize_macos_release.sh` fails closed when a Developer ID Application identity or stored `notarytool` profile is missing; it never accepts credentials on the command line or prints secret material.

The signing sequence for a future distributable is: build Release, sign nested runtime components, sign the app with Developer ID Application, verify with `codesign`, create and sign the DMG, submit with a Keychain `notarytool` profile, wait, staple, and run Gatekeeper assessment.

## Delivery gaps

- P1: Developer ID Application identity, installer signing identity, notarization profile, and Gatekeeper validation are unavailable in this environment.
- P1: no updater is integrated; update signing and feed ownership must be decided before beta distribution.
- P2: onboarding, licensing, and polished installer UI remain foundation work.
