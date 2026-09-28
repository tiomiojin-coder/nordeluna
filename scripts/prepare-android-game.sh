#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 2 ]; then
  echo "uso: $0 ARQUIVO-DE-ENTRADA.zip ARQUIVO-DE-SAIDA.zip" >&2
  exit 2
fi

INPUT_ARCHIVE="$(realpath "$1")"
OUTPUT_ARCHIVE="$(realpath -m "$2")"
WORK_DIR="$(mktemp -d)"
GAME_DIR="$WORK_DIR/game"
trap 'rm -rf "$WORK_DIR"' EXIT INT TERM

for command in unzip zip ffmpeg fluidsynth; do
  command -v "$command" >/dev/null || {
    echo "error: comando obrigatório ausente: $command" >&2
    exit 1
  }
done

mkdir -p "$GAME_DIR"
unzip -q "$INPUT_ARCHIVE" -d "$GAME_DIR"

test -f "$GAME_DIR/Game.ini"
test -f "$GAME_DIR/Data/Scripts.rxdata"
test -f "$GAME_DIR/soundfont.sf2"

# The pinned Android mkxp-z build has no FluidSynth shared library. Render the
# game's MIDI files with its own SoundFont so those tracks are not silent.
midi_count=0
while IFS= read -r -d '' midi_file; do
  ogg_file="${midi_file%.*}.ogg"
  wav_file="$WORK_DIR/midi-$midi_count.wav"

  fluidsynth -ni -r 44100 -F "$wav_file" \
    "$GAME_DIR/soundfont.sf2" "$midi_file" >/dev/null 2>&1
  ffmpeg -nostdin -loglevel error -y -i "$wav_file" \
    -map_metadata -1 -c:a libvorbis -q:a 5 "$ogg_file"
  rm -f "$wav_file" "$midi_file"
  midi_count=$((midi_count + 1))
done < <(find "$GAME_DIR/Audio" -type f \( -iname '*.mid' -o -iname '*.midi' \) -print0)

# Essentials 21.1 does not include MP3 in its normal extension search list.
# Add an OGG sibling while retaining the original for compatibility.
mp3_count=0
while IFS= read -r -d '' mp3_file; do
  ogg_file="${mp3_file%.*}.ogg"
  if [ ! -f "$ogg_file" ]; then
    ffmpeg -nostdin -loglevel error -y -i "$mp3_file" \
      -map_metadata -1 -c:a libvorbis -q:a 5 "$ogg_file"
    mp3_count=$((mp3_count + 1))
  fi
done < <(find "$GAME_DIR/Audio" -type f -iname '*.mp3' -print0)

# More simultaneous sound-effect sources help Essentials scenes that layer
# menu, battle and ambient effects. Path caching also fixes case-sensitive and
# accented filename lookups after extraction on Android/Linux.
sed -i 's|^[[:space:]]*// "SESourceCount": 6,|    "SESourceCount": 16,|' "$GAME_DIR/mkxp.json"
sed -i 's|^[[:space:]]*// "pathCache": true,|    "pathCache": true,|' "$GAME_DIR/mkxp.json"

rm -f "$OUTPUT_ARCHIVE"
(cd "$GAME_DIR" && zip -q -X -r "$OUTPUT_ARCHIVE" .)

unzip -tq "$OUTPUT_ARCHIVE"
test "$(find "$GAME_DIR/Audio" -type f \( -iname '*.mid' -o -iname '*.midi' \) | wc -l)" -eq 0

echo "Pacote Android preparado: $midi_count MIDI e $mp3_count MP3 convertidos para OGG"
