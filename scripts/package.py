#!/usr/bin/env python3
from __future__ import annotations

import os
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ADDON = ET.parse(ROOT / "addon.xml").getroot()
ADDON_ID = ADDON.attrib["id"]
VERSION = ADDON.attrib["version"]
OUTPUT_DIR = ROOT / "dist"
OUTPUT = OUTPUT_DIR / f"{ADDON_ID}-{VERSION}.zip"

INCLUDED_ROOT_FILES = ("addon.xml", "context.py", "default.py", "LICENSE")
INCLUDED_ROOT_DIRS = ("resources",)
MIN_ZIP_EPOCH = 315532800  # 1980-01-01, the earliest ZIP timestamp.
MAX_ZIP_EPOCH = 4354819198  # 2107-12-31 23:59:58 UTC.


def _zip_timestamp() -> tuple[int, int, int, int, int, int]:
    default_epoch = int((ROOT / "addon.xml").stat().st_mtime)
    epoch = int(os.environ.get("SOURCE_DATE_EPOCH", default_epoch))
    epoch = min(max(epoch, MIN_ZIP_EPOCH), MAX_ZIP_EPOCH)
    timestamp = datetime.fromtimestamp(epoch, timezone.utc)
    return (timestamp.year, timestamp.month, timestamp.day,
            timestamp.hour, timestamp.minute, timestamp.second // 2 * 2)


def _iter_runtime_files():
    for name in INCLUDED_ROOT_FILES:
        path = ROOT / name
        if not path.is_file():
            raise FileNotFoundError(f"Required package file is missing: {path}")
        yield path

    for name in INCLUDED_ROOT_DIRS:
        directory = ROOT / name
        if not directory.is_dir():
            raise FileNotFoundError(f"Required package directory is missing: {directory}")
        for path in sorted(directory.rglob("*")):
            if path.is_file() and path.suffix not in {".pyc", ".pyo"}:
                yield path


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    temporary = OUTPUT.with_name(OUTPUT.name + ".tmp")
    timestamp = _zip_timestamp()

    try:
        with zipfile.ZipFile(temporary, "w") as archive:
            for source in sorted(_iter_runtime_files()):
                relative = source.relative_to(ROOT).as_posix()
                archive_name = f"{ADDON_ID}/{relative}"
                info = zipfile.ZipInfo(archive_name, timestamp)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.create_system = 3
                info.flag_bits |= 0x800  # UTF-8 filenames.
                mode = source.stat().st_mode & 0o777
                info.external_attr = ((0o100000 | mode) & 0xFFFF) << 16
                archive.writestr(
                    info,
                    source.read_bytes(),
                    compress_type=zipfile.ZIP_DEFLATED,
                    compresslevel=9,
                )
        os.replace(temporary, OUTPUT)
    finally:
        if temporary.exists():
            temporary.unlink()

    print(OUTPUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
