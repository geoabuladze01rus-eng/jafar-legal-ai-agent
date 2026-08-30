#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if ! command -v xcodegen >/dev/null 2>&1; then
  echo "xcodegen is required (brew install xcodegen)" >&2
  exit 2
fi

(
  cd apple
  xcodegen generate --spec project.yml
)

test -d apple/JafarApp.xcodeproj
xcodebuild -project apple/JafarApp.xcodeproj -list
xcodebuild -project apple/JafarApp.xcodeproj -target JafarApp_iOS \
  -sdk iphonesimulator -destination 'generic/platform=iOS Simulator' \
  CODE_SIGNING_ALLOWED=NO build
xcodebuild -project apple/JafarApp.xcodeproj -target JafarApp_macOS \
  -sdk macosx -destination 'platform=macOS' CODE_SIGNING_ALLOWED=NO build
