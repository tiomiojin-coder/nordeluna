#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PARTS_DIR="$REPO_ROOT/game-assets"
DEST="$REPO_ROOT/ios/Nordeluna/BundledGame"
WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT INT TERM

shopt -s nullglob
PARTS=("$PARTS_DIR"/game-assets.zip.part*)
if [ "${#PARTS[@]}" -eq 0 ]; then
  echo "error: nenhuma parte encontrada em game-assets/" >&2
  echo "execute scripts/prepare-nordeluna-assets.ps1 no Windows primeiro" >&2
  exit 1
fi

cat "${PARTS[@]}" > "$WORK_DIR/game-assets.zip"
(cd "$WORK_DIR" && shasum -a 256 -c "$PARTS_DIR/sha256.txt")

rm -rf "$DEST"
mkdir -p "$DEST"
ditto -x -k "$WORK_DIR/game-assets.zip" "$DEST"

test -f "$DEST/Game.ini"
test -f "$DEST/Data/Scripts.rxdata"
echo "Nordeluna reconstruído em $DEST"
