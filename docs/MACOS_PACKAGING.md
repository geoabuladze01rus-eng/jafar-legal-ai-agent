# macOS commercial packaging foundation

## Current application architecture

The XcodeGen project defines `JafarApp_macOS` and `JafarApp_iOS`, bundle identifier `ru.jafar.legal-ai`, Swift 5.10, and minimum macOS 14.0. The macOS application is a SwiftUI voice client. It accepts a loopback or HTTPS command endpoint from `JAFAR_COMMAND_ENDPOINT`; without one it uses an in-process local command client. The Python legal backend is not embedded in the application bundle and is not launched by the app.

That last boundary is intentional for this foundation: the current artifact is a signed-ready client shell, not yet a standalone commercial legal workstation. A future beta must add a separately signed, managed local backend sidecar (or a carefully selected arm64 bundling approach) before claiming offline end-to-end legal analysis.

## Reproducible local artifact

On an Apple Silicon Mac with Xcode, XcodeGen, and `hdiutil` installed:

```bash
./scripts/build_macos_release.sh
```

The script generates the project, builds Release arm64 with signing disabled, validates metadata and privacy keys, rejects credential/developer-path markers, creates an Applications-link DMG, mounts and unmounts it, and writes a SHA-256 sidecar. Output is under `dist/macos/`, which is ignored and must never be committed or attached to the stable `v2.0.0` release.

The current output is explicitly an unsigned beta/local artifact. It is not a commercial distribution.

## Signing and notarization

`ENABLE_HARDENED_RUNTIME=YES` is set in the generated target settings. No entitlements or broad exceptions are currently required. `scripts/notarize_macos_release.sh` fails closed when a Developer ID Application identity or stored `notarytool` profile is missing; it never accepts credentials on the command line or prints secret material.

The signing sequence for a future distributable is: build Release, sign nested runtime components, sign the app with Developer ID Application, verify with `codesign`, create and sign the DMG, submit with a Keychain `notarytool` profile, wait, staple, and run Gatekeeper assessment.

## Delivery gaps

- P0: the Python backend is not embedded or managed by the packaged app, so a clean Mac receives a client shell rather than a complete standalone legal application.
- P1: Developer ID Application identity, installer signing identity, notarization profile, and Gatekeeper validation are unavailable in this environment.
- P1: no updater is integrated; update signing and feed ownership must be decided before beta distribution.
- P2: onboarding, licensing, and polished installer UI remain foundation work.
