#!/usr/bin/env python3
"""Create a deterministic ZIP whose non-ASCII paths use ZIP UTF-8 flags."""

from __future__ import annotations

import argparse
import os
import tempfile
import unicodedata
import zipfile
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    source = args.source.resolve(strict=True)
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{output.name}.", suffix=".tmp", dir=output.parent
    )
    os.close(fd)
    temporary = Path(temporary_name)

    try:
        with zipfile.ZipFile(
            temporary,
            "w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=6,
            allowZip64=True,
        ) as archive:
            for path in sorted(source.rglob("*")):
                if not path.is_file():
                    continue
                name = unicodedata.normalize(
                    "NFC", path.relative_to(source).as_posix()
                )
                archive.write(path, name)

        with zipfile.ZipFile(temporary, "r") as check:
            bad_file = check.testzip()
            if bad_file is not None:
                raise ValueError(f"corrupt file after packaging: {bad_file}")
            names = check.namelist()
            if any("\ufffd" in name for name in names):
                raise ValueError("replacement character found in Android archive")
            if any(name.lower().endswith((".mid", ".midi")) for name in names):
                raise ValueError("unconverted MIDI file found in Android archive")

            laboratory = "Graphics/Pictures/Laborat\u00f3rio (Intro).png"
            if laboratory not in names:
                raise ValueError("intro laboratory background is missing")
            if not check.getinfo(laboratory).flag_bits & 0x800:
                raise ValueError("intro laboratory path is not flagged as UTF-8")
            if "Audio/BGM/Lab.ogg" not in names:
                raise ValueError("intro music was not converted to OGG")

        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
