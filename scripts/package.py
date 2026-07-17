#!/usr/bin/env python3
from __future__ import annotations

import os
import stat
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
INCLUDED_ROOT_FILES = ("addon.xml", "context.py", "default.py", "LICENSE.txt")
INCLUDED_ROOT_DIRS = ("resources",)
ALLOWED_SUFFIXES = {".py", ".xml", ".po", ".png", ".jpg", ".jpeg"}
MIN_ZIP_EPOCH = 315532800
MAX_ZIP_EPOCH = 4354819198
PACKAGE_FILE_MODE = 0o644


def _zip_timestamp():
    default_epoch = int((ROOT / "addon.xml").stat().st_mtime)
    epoch = int(os.environ.get("SOURCE_DATE_EPOCH", default_epoch))
    epoch = min(max(epoch, MIN_ZIP_EPOCH), MAX_ZIP_EPOCH)
    timestamp = datetime.fromtimestamp(epoch, timezone.utc)
    return (timestamp.year, timestamp.month, timestamp.day, timestamp.hour, timestamp.minute, timestamp.second // 2 * 2)


def _iter_runtime_files():
    for name in INCLUDED_ROOT_FILES:
        path = ROOT / name
        if not path.is_file() or path.is_symlink():
            raise FileNotFoundError(f"Required package file is missing or unsafe: {path}")
        yield path
    for name in INCLUDED_ROOT_DIRS:
        directory = ROOT / name
        if not directory.is_dir() or directory.is_symlink():
            raise FileNotFoundError(f"Required package directory is missing or unsafe: {directory}")
        for path in sorted(directory.rglob("*")):
            if path.is_symlink():
                raise RuntimeError(f"Symlinks are not allowed in the package: {path}")
            if not path.is_file():
                continue
            relative_parts = path.relative_to(ROOT).parts
            if '__pycache__' in relative_parts or path.suffix.lower() in {'.pyc', '.pyo'}:
                continue
            if any(part.startswith(".") for part in relative_parts):
                raise RuntimeError(f"Hidden files are not allowed in the package: {path}")
            if path.suffix.lower() not in ALLOWED_SUFFIXES:
                raise RuntimeError(f"Unexpected runtime file type: {path}")
            yield path


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    temporary = OUTPUT.with_name(OUTPUT.name + ".tmp")
    timestamp = _zip_timestamp()
    try:
        with zipfile.ZipFile(temporary, "w") as archive:
            for source in sorted(_iter_runtime_files()):
                relative = source.relative_to(ROOT).as_posix()
                info = zipfile.ZipInfo(f"{ADDON_ID}/{relative}", timestamp)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.create_system = 3
                info.flag_bits |= 0x800
                info.external_attr = ((stat.S_IFREG | PACKAGE_FILE_MODE) & 0xFFFF) << 16
                archive.writestr(info, source.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
        os.replace(temporary, OUTPUT)
    finally:
        if temporary.exists():
            temporary.unlink()
    print(OUTPUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
