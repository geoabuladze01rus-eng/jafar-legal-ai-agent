#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APPLE_DIR="$ROOT_DIR/apple"
DIST_DIR="${JAFAR_DIST_DIR:-$ROOT_DIR/dist/macos}"
PACKAGE_VERSION="${JAFAR_PACKAGE_VERSION:-2.1.0-beta.1}"
ARCH="${JAFAR_MACOS_ARCH:-arm64}"
APP_NAME="JAFAR.app"
DMG_NAME="JAFAR-${PACKAGE_VERSION}-macos-${ARCH}.dmg"
BUILD_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/jafar-macos-build.XXXXXX")"
PROJECT_PATH="$APPLE_DIR/JafarApp.xcodeproj"

cleanup() {
  rm -rf "$BUILD_ROOT"
  if [[ -d "$PROJECT_PATH" ]]; then
    rm -rf "$PROJECT_PATH"
  fi
}
trap cleanup EXIT

die() {
  echo "error: $*" >&2
  exit 1
}

command -v xcodegen >/dev/null || die "xcodegen is required"
command -v xcodebuild >/dev/null || die "xcodebuild is required"
command -v hdiutil >/dev/null || die "hdiutil is required on macOS"
command -v shasum >/dev/null || die "shasum is required"
command -v strip >/dev/null || die "strip is required on macOS"

[[ "$(uname -s)" == "Darwin" ]] || die "macOS packaging must run on macOS"
[[ "$ARCH" == "arm64" ]] || die "only Apple Silicon arm64 is supported by this beta foundation"

mkdir -p "$DIST_DIR"
rm -rf "$DIST_DIR/$APP_NAME" "$DIST_DIR/$DMG_NAME" "$DIST_DIR/$DMG_NAME.sha256"

BACKEND_DIR="${JAFAR_BACKEND_DIR:-$ROOT_DIR/dist/backend/JafarBackend}"
if [[ -z "${JAFAR_BACKEND_DIR:-}" ]]; then
  JAFAR_MACOS_ARCH="$ARCH" "$ROOT_DIR/scripts/build_macos_backend.sh"
fi
[[ -x "$BACKEND_DIR/JafarBackend" ]] || die "standalone backend sidecar was not produced"

cd "$APPLE_DIR"
xcodegen generate --spec project.yml >/dev/null
xcodebuild \
  -project "$PROJECT_PATH" \
  -target JafarApp_macOS \
  -configuration Release \
  -sdk macosx \
  ARCHS="$ARCH" \
  ONLY_ACTIVE_ARCH=YES \
  CODE_SIGNING_ALLOWED=NO \
  SYMROOT="$BUILD_ROOT/sym" \
  OBJROOT="$BUILD_ROOT/obj" \
  build >/dev/null

BUILT_APP="$BUILD_ROOT/sym/Release/$APP_NAME"
[[ -d "$BUILT_APP" ]] || die "Release app was not produced"
# Strip source-level debug metadata from the distributable binary.  Debug symbols,
# when needed, must remain in the build archive rather than the customer artifact.
strip -S "$BUILT_APP/Contents/MacOS/Jafar"

version="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "$BUILT_APP/Contents/Info.plist")"
bundle_id="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleIdentifier' "$BUILT_APP/Contents/Info.plist")"
minimum_macos="$(/usr/libexec/PlistBuddy -c 'Print :LSMinimumSystemVersion' "$BUILT_APP/Contents/Info.plist")"
[[ "$version" == "2.1.0" ]] || die "unexpected app version: $version"
[[ "$bundle_id" == "ru.jafar.legal-ai" ]] || die "unexpected bundle identifier"
[[ "$minimum_macos" == "14.0" ]] || die "unexpected minimum macOS version: $minimum_macos"

if find "$BUILT_APP" -name .env -o -name .git -o -name '*.pem' -o -name '*.p12' | grep -q .; then
  die "forbidden credential or repository artifact found in app bundle"
fi
if strings "$BUILT_APP/Contents/MacOS/Jafar" | rg -q '/Users/|/var/folders/|sk-(proj-)?[A-Za-z0-9_-]{20,}|GOCSPX-'; then
  die "sensitive development path or credential marker found in app binary"
fi

HELPERS_DIR="$BUILT_APP/Contents/Resources/Helpers"
mkdir -p "$HELPERS_DIR"
ditto "$BACKEND_DIR" "$HELPERS_DIR/JafarBackend"
[[ -x "$HELPERS_DIR/JafarBackend/JafarBackend" ]] || die "backend sidecar was not embedded"
file "$HELPERS_DIR/JafarBackend/JafarBackend" | grep -q 'arm64' || die "embedded backend is not arm64"

while IFS= read -r forbidden; do
  # certifi's public CA bundle is required for TLS verification; it contains no private key.
  [[ "$forbidden" == "$BUILT_APP/Contents/Resources/Helpers/JafarBackend/_internal/certifi/cacert.pem" ]] && continue
  die "forbidden credential or repository artifact found after backend embedding"
done < <(find "$BUILT_APP" \( -name .env -o -name .git -o -name '*.pem' -o -name '*.p12' \) -print)
for forbidden_path in "$ROOT_DIR" "$HOME"; do
  if rg -a -F -l "$forbidden_path" "$BUILT_APP" >/dev/null; then
    die "local development path found in app bundle"
  fi
done
if rg -a -l 'sk-(proj-)?[A-Za-z0-9_-]{20,}|GOCSPX-' "$BUILT_APP" >/dev/null; then
  die "credential marker found in app bundle"
fi

ditto "$BUILT_APP" "$DIST_DIR/$APP_NAME"
STAGING_DIR="$BUILD_ROOT/staging"
mkdir -p "$STAGING_DIR"
ditto "$BUILT_APP" "$STAGING_DIR/$APP_NAME"
ln -s /Applications "$STAGING_DIR/Applications"

DMG_PATH="$DIST_DIR/$DMG_NAME"
hdiutil create \
  -volname "JAFAR ${PACKAGE_VERSION}" \
  -srcfolder "$STAGING_DIR" \
  -format UDZO \
  -ov "$DMG_PATH" >/dev/null

MOUNT_OUTPUT="$(hdiutil attach -nobrowse -readonly "$DMG_PATH")"
MOUNT_POINT="$(printf '%s\n' "$MOUNT_OUTPUT" | awk '/\/Volumes\// {print substr($0, index($0, "/Volumes/"))}' | tail -1)"
[[ -n "$MOUNT_POINT" && -d "$MOUNT_POINT/$APP_NAME" && -L "$MOUNT_POINT/Applications" ]] || {
  [[ -z "$MOUNT_POINT" ]] || hdiutil detach "$MOUNT_POINT" >/dev/null || true
  die "DMG mount validation failed"
}
hdiutil detach "$MOUNT_POINT" >/dev/null

shasum -a 256 "$DMG_PATH" > "$DMG_PATH.sha256"
echo "UNSIGNED_LOCAL_ARTIFACT=$DMG_PATH"
echo "APP_PATH=$DIST_DIR/$APP_NAME"
echo "VERSION=$version"
echo "BUNDLE_ID=$bundle_id"
echo "MINIMUM_MACOS=$minimum_macos"
echo "SHA256=$(awk '{print $1}' "$DMG_PATH.sha256")"
echo "WARNING=unsigned local beta artifact; not suitable for stable commercial distribution"
