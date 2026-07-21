#!/usr/bin/env python3
from __future__ import annotations

import os
import re
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
ROOT_CONTEXT_LABEL = "* Managarr"
EXPECTED_CONTEXT_ACTIONS = {
    "status",
    "search_now",
    "monitor",
    "unmonitor",
    "change_quality_profile",
    "queue_view",
    "queue_remove",
    "delete_exclude",
    "delete_replace",
}
EXPECTED_CONTEXT_SUBMENUS = {
    "32005": {"monitor", "unmonitor", "change_quality_profile"},
    "32009": {"queue_view", "queue_remove"},
}


def _zip_timestamp():
    default_epoch = int((ROOT / "addon.xml").stat().st_mtime)
    epoch = int(os.environ.get("SOURCE_DATE_EPOCH", default_epoch))
    epoch = min(max(epoch, MIN_ZIP_EPOCH), MAX_ZIP_EPOCH)
    timestamp = datetime.fromtimestamp(epoch, timezone.utc)
    return (
        timestamp.year,
        timestamp.month,
        timestamp.day,
        timestamp.hour,
        timestamp.minute,
        timestamp.second // 2 * 2,
    )


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
            if "__pycache__" in relative_parts or path.suffix.lower() in {".pyc", ".pyo"}:
                continue
            if any(part.startswith(".") for part in relative_parts):
                raise RuntimeError(f"Hidden files are not allowed in the package: {path}")
            if path.suffix.lower() not in ALLOWED_SUFFIXES:
                raise RuntimeError(f"Unexpected runtime file type: {path}")
            yield path


def _validate_packaged_context(archive, addon):
    extension = addon.find("extension[@point='kodi.context.item']")
    if extension is None:
        raise RuntimeError("Packaged addon.xml is missing kodi.context.item")
    root_menu = extension.find("menu[@id='kodi.core.main']")
    if root_menu is None:
        raise RuntimeError("Packaged addon.xml is missing kodi.core.main")
    branding_menus = root_menu.findall("menu")
    if len(branding_menus) != 1:
        raise RuntimeError("Packaged kodi.core.main must contain one Managarr root submenu")
    branding_menu = branding_menus[0]
    root_label = (branding_menu.findtext("label") or "").strip()
    if root_label != ROOT_CONTEXT_LABEL or not root_label.isascii():
        raise RuntimeError(f"Packaged context root label must be exactly {ROOT_CONTEXT_LABEL!r}")

    items = branding_menu.findall(".//item")
    actions = {item.attrib.get("args", "") for item in items}
    if actions != EXPECTED_CONTEXT_ACTIONS:
        raise RuntimeError(
            "Packaged context actions are incorrect: "
            f"expected {sorted(EXPECTED_CONTEXT_ACTIONS)}, got {sorted(actions)}"
        )
    if any(item.attrib.get("library") != "context.py" for item in items):
        raise RuntimeError("Every packaged context item must dispatch through context.py")
    if any(not (item.findtext("visible") or "").strip() for item in items):
        raise RuntimeError("Every packaged context item must define a visibility expression")

    nested = branding_menu.findall("menu")
    labels = {(submenu.findtext("label") or "").strip() for submenu in nested}
    if labels != set(EXPECTED_CONTEXT_SUBMENUS):
        raise RuntimeError("Packaged context submenu labels are incorrect")
    for submenu in nested:
        label = (submenu.findtext("label") or "").strip()
        submenu_actions = {item.attrib.get("args", "") for item in submenu.findall("item")}
        if submenu_actions != EXPECTED_CONTEXT_SUBMENUS[label]:
            raise RuntimeError(f"Packaged context submenu {label} contains incorrect actions")

    po_path = f"{ADDON_ID}/resources/language/resource.language.en_gb/strings.po"
    po_text = archive.read(po_path).decode("utf-8")
    po_ids = {int(value) for value in re.findall(r'^msgctxt "#([0-9]+)"$', po_text, flags=re.M)}
    numeric_labels = {
        int(value)
        for value in ((node.text or "").strip() for node in extension.findall(".//label"))
        if value.isdigit()
    }
    missing = sorted(numeric_labels - po_ids)
    if missing:
        raise RuntimeError(f"Packaged context labels are missing from strings.po: {missing}")


def _validate_archive(path):
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("Generated package failed ZIP integrity validation")
        required = {
            f"{ADDON_ID}/addon.xml",
            f"{ADDON_ID}/context.py",
            f"{ADDON_ID}/default.py",
            f"{ADDON_ID}/resources/settings.xml",
            f"{ADDON_ID}/resources/language/resource.language.en_gb/strings.po",
        }
        names = set(archive.namelist())
        missing = sorted(required - names)
        if missing:
            raise RuntimeError(f"Generated package is missing required files: {missing}")
        addon = ET.fromstring(archive.read(f"{ADDON_ID}/addon.xml"))
        if addon.attrib.get("id") != ADDON_ID or addon.attrib.get("version") != VERSION:
            raise RuntimeError("Packaged addon.xml identity/version does not match the build")
        _validate_packaged_context(archive, addon)


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
                archive.writestr(
                    info,
                    source.read_bytes(),
                    compress_type=zipfile.ZIP_DEFLATED,
                    compresslevel=9,
                )
        _validate_archive(temporary)
        os.replace(temporary, OUTPUT)
    finally:
        if temporary.exists():
            temporary.unlink()
    print(OUTPUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
