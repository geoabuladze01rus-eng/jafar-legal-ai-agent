#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST_DIR="${JAFAR_DIST_DIR:-$ROOT_DIR/dist/macos}"
APP_PATH="$DIST_DIR/JAFAR.app"
IDENTITY="${JAFAR_DEVELOPER_ID_IDENTITY:-}"
NOTARY_PROFILE="${NOTARY_PROFILE:-}"

die() { echo "error: $*" >&2; exit 2; }

"$ROOT_DIR/scripts/build_macos_release.sh"
[[ -d "$APP_PATH" ]] || die "unsigned app was not produced"
command -v codesign >/dev/null || die "Xcode signing tools are unavailable"

echo "Nested executable inventory (inside-out signing order):"
while IFS= read -r component; do
  file "$component" | grep -q 'Mach-O' && echo "  $component"
done < <(find "$APP_PATH" -type f -print)

if [[ -z "$IDENTITY" ]] || ! security find-identity -v -p codesigning 2>/dev/null | rg -F "$IDENTITY" >/dev/null; then
  die "Developer ID Application identity is unavailable; unsigned artifact was built and no signing/notarization was attempted"
fi
[[ -n "$NOTARY_PROFILE" ]] || die "NOTARY_PROFILE is unavailable; no signing/notarization was attempted"

die "distribution submission requires a separately authorized release invocation"
