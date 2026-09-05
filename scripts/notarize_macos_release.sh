#!/usr/bin/env bash
set -euo pipefail

APP_PATH="${1:-}"
NOTARY_PROFILE="${NOTARY_PROFILE:-}"

if [[ -z "$APP_PATH" || ! -d "$APP_PATH" ]]; then
  echo "error: pass an existing JAFAR.app path" >&2
  exit 2
fi
if ! command -v codesign >/dev/null || ! command -v xcrun >/dev/null; then
  echo "signing/notarization prerequisites missing: Xcode tooling" >&2
  exit 2
fi
if ! security find-identity -v -p codesigning 2>/dev/null | rg -q 'Developer ID Application'; then
  echo "signing/notarization prerequisites missing: Developer ID Application identity" >&2
  exit 2
fi
if [[ -z "$NOTARY_PROFILE" ]]; then
  echo "signing/notarization prerequisites missing: NOTARY_PROFILE" >&2
  exit 2
fi

echo "Signing/notarization foundation detected. A production signing command requires an explicit release invocation."
echo "No submission was performed by this foundation script."
