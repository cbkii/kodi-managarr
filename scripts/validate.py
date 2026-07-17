#!/usr/bin/env python3
import compileall
import importlib.util
import os
import re
import shutil
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent


def main():
    addon = ET.parse(ROOT / "addon.xml").getroot()
    settings = ET.parse(ROOT / "resources/settings.xml").getroot()
    if addon.attrib.get("id") != "context.arr.manager":
        raise SystemExit("Unexpected add-on ID")
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", addon.attrib.get("version", "")):
        raise SystemExit("addon.xml version must use x.y.z")
    if settings.attrib.get("version") != "1" or settings.find("section[@id='context.arr.manager']") is None:
        raise SystemExit("resources/settings.xml must use the Kodi Matrix+ version 1 schema")
    print("OK XML and metadata")

    if not compileall.compile_dir(str(ROOT), quiet=1, rx=re.compile(r"[\\/]\.git[\\/]")):
        raise SystemExit("Python compilation failed")
    _remove_bytecode(ROOT)
    print("OK Python compilation")

    required = [
        "addon.xml", "context.py", "default.py", "LICENSE.txt", "resources/icon.png",
        "resources/fanart.jpg", "resources/settings.xml",
        "resources/language/resource.language.en_gb/strings.po",
    ]
    missing = [path for path in required if not (ROOT / path).is_file()]
    if missing:
        raise SystemExit("Missing required files: " + ", ".join(missing))
    _validate_images()
    _validate_context_items(addon)
    _validate_strings(addon, settings)
    _validate_spdx()
    print("OK required files, images, context items, strings and SPDX headers")
    return 0


def _validate_images():
    with Image.open(ROOT / "resources/icon.png") as image:
        if image.size != (512, 512) or image.format != "PNG":
            raise SystemExit("icon.png must be a 512x512 PNG")
        if image.mode not in {"RGB", "P"}:
            raise SystemExit("icon.png must be opaque")
        if image.mode == "P" and "transparency" in image.info:
            raise SystemExit("icon.png must not contain transparency")
    with Image.open(ROOT / "resources/fanart.jpg") as image:
        if image.size != (1920, 1080) or image.format != "JPEG":
            raise SystemExit("fanart.jpg must be a 1920x1080 JPEG")


def _validate_context_items(addon):
    seen = set()
    for item in addon.findall(".//extension[@point='kodi.context.item']//item"):
        key = (item.attrib.get("library"), item.attrib.get("args", ""))
        if not key[0] or key in seen:
            raise SystemExit(f"Duplicate or invalid context item: {key}")
        seen.add(key)
        visible = item.find("visible")
        if visible is None or not (visible.text or "").strip():
            raise SystemExit(f"Context item {key} is missing a visible expression")


def _po_entries(path):
    content = path.read_text(encoding="utf-8")
    if "\r" in content:
        raise SystemExit("strings.po must use Unix line endings")
    blocks = [block for block in re.split(r"\n[ \t]*\n", content) if block.strip()]
    entries = []
    for index, block in enumerate(blocks):
        contexts = re.findall(r'^msgctxt "#([0-9]+)"$', block, flags=re.M)
        if not contexts:
            if index == 0 and re.search(r'^msgid ""$', block, flags=re.M):
                continue
            raise SystemExit("strings.po contains a block without a numeric msgctxt")
        if len(contexts) != 1:
            joined = ", ".join(contexts)
            raise SystemExit(
                "strings.po entries must be separated by a blank line; "
                f"one block contains IDs: {joined}"
            )
        msgids = re.findall(r'^msgid "(.*)"$', block, flags=re.M)
        if not msgids or not msgids[0]:
            raise SystemExit(f"Language string #{contexts[0]} has an empty or missing msgid")
        entries.append((int(contexts[0]), block))
    if not entries:
        raise SystemExit("strings.po contains no localised strings")
    return entries


def _po_ids(path):
    values = [string_id for string_id, _ in _po_entries(path)]
    duplicates = sorted({value for value in values if values.count(value) > 1})
    if duplicates:
        raise SystemExit(f"Duplicate language string IDs: {duplicates}")
    return set(values)


def _setting_string_id(node, attribute):
    value = node.attrib.get(attribute, "").strip()
    if not value.isdigit() or int(value) < 30000:
        raise SystemExit(
            f"Settings {node.tag} '{node.attrib.get('id', '')}' must define a localised {attribute} ID"
        )
    return int(value)


def _validate_strings(addon, settings):
    ids = _po_ids(ROOT / "resources/language/resource.language.en_gb/strings.po")
    referenced = set()
    for node in addon.iter("label"):
        value = (node.text or "").strip()
        if value.isdigit() and int(value) >= 30000:
            referenced.add(int(value))
    for node in settings.iter():
        for attribute in ("label", "help"):
            value = node.attrib.get(attribute, "").strip()
            if value.isdigit() and int(value) >= 30000:
                referenced.add(int(value))
    for node in settings.findall(".//category") + settings.findall(".//setting"):
        referenced.add(_setting_string_id(node, "label"))
        referenced.add(_setting_string_id(node, "help"))
    spec = importlib.util.spec_from_file_location(
        "arr_manager_messages", ROOT / "resources/lib/arr_manager/messages.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    referenced.update(string_id for string_id, _ in module.MESSAGES.values())
    missing = sorted(referenced - ids)
    if missing:
        raise SystemExit(f"Missing language strings: {missing}")


def _validate_spdx():
    files = [ROOT / "context.py", ROOT / "default.py"]
    files.extend((ROOT / "resources/lib/arr_manager").glob("*.py"))
    for path in files:
        first_lines = "\n".join(path.read_text(encoding="utf-8").splitlines()[:3])
        if "SPDX-License-Identifier: GPL-3.0-or-later" not in first_lines:
            raise SystemExit(f"Missing SPDX header: {path.relative_to(ROOT)}")


def _remove_bytecode(root):
    for dirpath, dirnames, filenames in os.walk(root, topdown=True):
        for ignored in (".git", "dist"):
            if ignored in dirnames:
                dirnames.remove(ignored)
        if "__pycache__" in dirnames:
            dirnames.remove("__pycache__")
            shutil.rmtree(Path(dirpath) / "__pycache__", ignore_errors=True)
        for filename in filenames:
            if filename.endswith((".pyc", ".pyo")):
                try:
                    (Path(dirpath) / filename).unlink()
                except OSError:
                    pass


if __name__ == "__main__":
    raise SystemExit(main())
