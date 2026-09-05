#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST_DIR="${JAFAR_BACKEND_DIST_DIR:-$ROOT_DIR/dist/backend}"
BUILD_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/jafar-backend-build.XXXXXX")"
BUILD_PYTHON="${JAFAR_BUILD_PYTHON:-python3}"
ARCH="${JAFAR_MACOS_ARCH:-arm64}"
OUTPUT_DIR="$DIST_DIR/JafarBackend"

cleanup() { rm -rf "$BUILD_ROOT"; }
trap cleanup EXIT

die() { echo "error: $*" >&2; exit 1; }

[[ "$(uname -s)" == "Darwin" ]] || die "macOS backend packaging must run on macOS"
[[ "$ARCH" == "arm64" ]] || die "only Apple Silicon arm64 is supported"
command -v "$BUILD_PYTHON" >/dev/null || die "Python 3.12 build interpreter is required"
command -v file >/dev/null || die "file is required"
command -v shasum >/dev/null || die "shasum is required"

PYTHON_VERSION="$($BUILD_PYTHON -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')"
[[ "$PYTHON_VERSION" == "3.12" ]] || die "Python 3.12 is required, found $PYTHON_VERSION"
[[ "$($BUILD_PYTHON -c 'import platform; print(platform.machine())')" == "arm64" ]] || die "arm64 Python is required"

rm -rf "$OUTPUT_DIR"
mkdir -p "$DIST_DIR"

if [[ -n "${JAFAR_BACKEND_BUILD_PYTHON:-}" ]]; then
  BUILD_VENV_PYTHON="$JAFAR_BACKEND_BUILD_PYTHON"
  "$BUILD_VENV_PYTHON" -c 'import PyInstaller' >/dev/null || die "configured build Python lacks PyInstaller"
else
  "$BUILD_PYTHON" -m venv "$BUILD_ROOT/venv"
  BUILD_VENV_PYTHON="$BUILD_ROOT/venv/bin/python"
  "$BUILD_VENV_PYTHON" -m pip install --disable-pip-version-check --no-input "$ROOT_DIR[macos-build]" >/dev/null
fi
PYINSTALLER_LOG="$BUILD_ROOT/pyinstaller.log"
if ! "$BUILD_VENV_PYTHON" -m PyInstaller \
  --noconfirm \
  --clean \
  --onedir \
  --name JafarBackend \
  --distpath "$DIST_DIR" \
  --workpath "$BUILD_ROOT/pyinstaller-work" \
  --specpath "$BUILD_ROOT" \
  --paths "$ROOT_DIR/src" \
  --hidden-import jafar.main \
  "$ROOT_DIR/scripts/desktop_sidecar_entry.py" >"$PYINSTALLER_LOG" 2>&1; then
  tail -n 80 "$PYINSTALLER_LOG" >&2
  die "PyInstaller failed"
fi

EXECUTABLE="$OUTPUT_DIR/JafarBackend"
[[ -x "$EXECUTABLE" ]] || die "backend executable was not produced"
file "$EXECUTABLE" | grep -q 'arm64' || die "backend executable is not arm64"

while IFS= read -r forbidden; do
  # certifi's public CA bundle is required for TLS verification; it contains no private key.
  [[ "$forbidden" == "$OUTPUT_DIR/_internal/certifi/cacert.pem" ]] && continue
  die "forbidden credential or repository artifact found in backend bundle"
done < <(find "$OUTPUT_DIR" \( -name .env -o -name .git -o -name '*.pem' -o -name '*.p12' \) -print)
for forbidden_path in "$ROOT_DIR" "$HOME"; do
  if rg -a -F -l "$forbidden_path" "$OUTPUT_DIR" >/dev/null; then
    die "local development path found in backend bundle"
  fi
done
if rg -a -l 'sk-(proj-)?[A-Za-z0-9_-]{20,}|GOCSPX-' "$OUTPUT_DIR" >/dev/null; then
  die "credential marker found in backend bundle"
fi

(
  cd "$OUTPUT_DIR"
  find . -type f -print | LC_ALL=C sort | while IFS= read -r component; do
    shasum -a 256 "$component"
  done
) > "$OUTPUT_DIR/runtime-manifest.sha256"
(
  cd "$OUTPUT_DIR"
  shasum -a 256 JafarBackend > JafarBackend.sha256
)

echo "BACKEND_PATH=$OUTPUT_DIR"
echo "BACKEND_EXECUTABLE=$EXECUTABLE"
echo "ARCH=$ARCH"
echo "PYTHON_VERSION=$PYTHON_VERSION"
echo "SHA256=$(awk '{print $1}' "$OUTPUT_DIR/JafarBackend.sha256")"
