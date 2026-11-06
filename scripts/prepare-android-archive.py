#!/usr/bin/env python3
"""Repackage Nordeluna with Android-safe UTF-8 paths and configuration."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import tempfile
import unicodedata
import zipfile
from pathlib import Path, PurePosixPath


LEGACY_FILENAME_ENCODING = "cp850"


def normalized_name(name: str) -> str:
    """Return a safe NFC-normalized archive path."""
    normalized = unicodedata.normalize("NFC", name.replace("\\", "/"))
    path = PurePosixPath(normalized)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"unsafe path in archive: {name!r}")
    return normalized


def copy_info(source: zipfile.ZipInfo, filename: str) -> zipfile.ZipInfo:
    """Copy stable ZIP metadata while allowing Python to emit UTF-8 names."""
    target = zipfile.ZipInfo(filename=filename, date_time=source.date_time)
    target.compress_type = source.compress_type
    target.comment = source.comment
    # Canonical Unix metadata: Info-ZIP on Linux can otherwise reinterpret
    # UTF-8 names from a Windows-host entry when its local header uses ZIP64.
    target.create_system = 3
    target.external_attr = ((0o40755 if filename.endswith("/") else 0o100644) << 16)
    if filename.endswith("/"):
        target.external_attr |= 0x10
    target.internal_attr = source.internal_attr
    target.file_size = source.file_size
    # Do not retain legacy Unicode/path extras. zipfile writes the normalized
    # filename itself and sets the UTF-8 flag whenever it is required.
    return target


def prepare_archive(input_path: Path, output_path: Path, config_path: Path) -> None:
    config = config_path.read_bytes()
    json.loads(config.decode("utf-8"))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{output_path.name}.", suffix=".tmp", dir=output_path.parent
    )
    os.close(fd)
    temporary_path = Path(temporary_name)

    repaired_names: list[str] = []
    seen: set[str] = set()
    config_replacements = 0

    try:
        # The original archive was made on Windows with CP850 filenames and
        # without ZIP's UTF-8 flag. Android's Java extractor otherwise turns
        # accented characters into U+FFFD, making referenced assets invisible.
        with zipfile.ZipFile(
            input_path, "r", metadata_encoding=LEGACY_FILENAME_ENCODING
        ) as source, zipfile.ZipFile(
            temporary_path, "w", allowZip64=True
        ) as target:
            for entry in source.infolist():
                name = normalized_name(entry.filename)
                key = name.casefold()
                if key in seen:
                    raise ValueError(f"duplicate normalized path: {name}")
                seen.add(key)

                if any(ord(character) > 127 for character in name):
                    repaired_names.append(name)

                out_info = copy_info(entry, name)
                if name.removeprefix("./") == "mkxp.json":
                    target.writestr(out_info, config)
                    config_replacements += 1
                    continue

                with source.open(entry, "r") as source_file, target.open(
                    out_info, "w"
                ) as target_file:
                    shutil.copyfileobj(source_file, target_file, length=1024 * 1024)

        if config_replacements != 1:
            raise ValueError(
                f"expected one mkxp.json, replaced {config_replacements}"
            )

        with zipfile.ZipFile(temporary_path, "r") as check:
            bad_file = check.testzip()
            if bad_file is not None:
                raise ValueError(f"corrupt file after repackaging: {bad_file}")
            entries = {
                info.filename.removeprefix("./"): info for info in check.infolist()
            }
            names = list(entries)
            if any("\ufffd" in name for name in names):
                raise ValueError("replacement character found after repackaging")

            required_assets = (
                "Game.ini", "Data/Scripts.rxdata", "mkxp.json",
            )
            for name in required_assets:
                if name not in entries:
                    raise ValueError(f"required Android asset is missing: {name}")
            # Scene-specific graphics may be renamed or removed by updates.
            # Validate every present Unicode path, not a fixed old asset list.
            for name, entry in entries.items():
                if any(ord(character) > 127 for character in name) and not entry.flag_bits & 0x800:
                    raise ValueError(f"asset path is not flagged as UTF-8: {name}")

        os.replace(temporary_path, output_path)
    finally:
        temporary_path.unlink(missing_ok=True)

    print(
        f"Android archive ready: {len(repaired_names)} accented paths encoded as UTF-8"
    )
    for name in repaired_names:
        print(f"  {name}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("config", type=Path)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    prepare_archive(args.input, args.output, args.config)
