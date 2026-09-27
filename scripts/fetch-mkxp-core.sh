#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="$REPO_ROOT/ios/Nordeluna/Frameworks"
WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT INT TERM

VERSION="0.7.0"
IPA="Empo-${VERSION}-unsigned.ipa"
URL="https://github.com/mateo-m/empo-app/releases/download/v${VERSION}/${IPA}"
EXPECTED_SHA256="ddeb96e54ddbdc3233e954b5b392b14660864e5ab79ccbb412cf25abd26e1ab0"

curl -fL --retry 3 -o "$WORK_DIR/$IPA" "$URL"
ACTUAL_SHA256="$(shasum -a 256 "$WORK_DIR/$IPA" | awk '{print $1}')"
if [ "$ACTUAL_SHA256" != "$EXPECTED_SHA256" ]; then
  echo "error: SHA-256 inesperado para $IPA" >&2
  echo "esperado: $EXPECTED_SHA256" >&2
  echo "obtido:   $ACTUAL_SHA256" >&2
  exit 1
fi

mkdir -p "$WORK_DIR/unpacked" "$DEST"
ditto -x -k "$WORK_DIR/$IPA" "$WORK_DIR/unpacked"
SOURCE="$WORK_DIR/unpacked/Payload/Empo.app/Frameworks/MkxpCore.framework"
test -f "$SOURCE/MkxpCore"
rm -rf "$DEST/MkxpCore.framework"
cp -R "$SOURCE" "$DEST/MkxpCore.framework"
echo "MkxpCore.framework $VERSION preparado."
