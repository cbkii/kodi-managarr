#!/usr/bin/env python3
import ast
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
LIB_DIR = ROOT / "resources" / "lib"
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

from arr_manager.context_manifest import EXPECTED_CONTEXT_ACTIONS, ROOT_CONTEXT_LABEL  # noqa: E402
from arr_manager.registry import ACTION_REGISTRY  # noqa: E402


def main():
    addon = ET.parse(ROOT / "addon.xml").getroot()
    settings = ET.parse(ROOT / "resources/settings.xml").getroot()
    if addon.attrib.get("id") != "context.arr.manager":
        raise SystemExit("Unexpected add-on ID")
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", addon.attrib.get("version", "")):
        raise SystemExit("addon.xml version must use x.y.z")
    if settings.attrib.get("version") != "1" or settings.find("section[@id='context.arr.manager']") is None:
        raise SystemExit("resources/settings.xml must use the Kodi Matrix+ version 1 schema")
    _validate_extensions(addon)
    print("OK XML and metadata")

    if not compileall.compile_dir(str(ROOT), quiet=1, rx=re.compile(r"[\\/]\.git[\\/]")):
        raise SystemExit("Python compilation failed")
    _remove_bytecode(ROOT)
    print("OK Python compilation")

    required = [
        "addon.xml",
        "context.py",
        "default.py",
        "subtitles.py",
        "LICENSE.txt",
        "resources/icon.png",
        "resources/fanart.jpg",
        "resources/settings.xml",
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


def _validate_extensions(addon):
    subtitle = addon.find("extension[@point='xbmc.subtitle.module']")
    if subtitle is None or subtitle.attrib.get("library") != "subtitles.py":
        raise SystemExit("addon.xml must register subtitles.py as xbmc.subtitle.module")
    script = addon.find("extension[@point='xbmc.python.script']")
    if script is None or script.attrib.get("library") != "default.py":
        raise SystemExit("addon.xml must register default.py as xbmc.python.script")


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
    extension = addon.find("extension[@point='kodi.context.item']")
    if extension is None:
        raise SystemExit("addon.xml is missing kodi.context.item")
    root_menu = extension.find("menu[@id='kodi.core.main']")
    if root_menu is None:
        raise SystemExit("Context extension is missing kodi.core.main")

    branding_items = root_menu.findall("item")
    if len(branding_items) != 1:
        raise SystemExit("kodi.core.main must contain exactly one Managarr root item")
    branding_item = branding_items[0]
    root_label = (branding_item.findtext("label") or "").strip()
    if root_label != ROOT_CONTEXT_LABEL:
        raise SystemExit(f"Context root label must be exactly {ROOT_CONTEXT_LABEL!r}")

    key = (branding_item.attrib.get("library"), branding_item.attrib.get("args", ""))
    if key[0] != "context.py" or not key[1]:
        raise SystemExit(f"Invalid context item: {key}")
    visible = branding_item.find("visible")
    if visible is None or not (visible.text or "").strip():
        raise SystemExit(f"Context item {key} is missing a visible expression")
    actions = {key[1]}
    if actions != EXPECTED_CONTEXT_ACTIONS:
        raise SystemExit(
            "Context actions do not match the required scope: "
            f"expected {sorted(EXPECTED_CONTEXT_ACTIONS)}, got {sorted(actions)}"
        )


def _po_quoted_value(block, keyword):
    lines = block.splitlines()
    for index, line in enumerate(lines):
        prefix = keyword + " "
        if not line.startswith(prefix):
            continue
        quoted_lines = [line[len(prefix):].strip()]
        for continuation in lines[index + 1:]:
            stripped = continuation.strip()
            if not stripped.startswith('"'):
                break
            quoted_lines.append(stripped)
        try:
            return "".join(ast.literal_eval(value) for value in quoted_lines)
        except (SyntaxError, ValueError) as exc:
            raise SystemExit(f"strings.po contains an invalid {keyword} value") from exc
    return None


def _po_entries(path):
    content = path.read_text(encoding="utf-8")
    if "\r" in content:
        raise SystemExit("strings.po must use Unix line endings")
    blocks = [block for block in re.split(r"\n[ \t]*\n", content) if block.strip()]
    entries = []
    for block in blocks:
        nonblank = [line.strip() for line in block.splitlines() if line.strip()]
        if nonblank and all(line.startswith("#") for line in nonblank):
            continue
        contexts = re.findall(r'^msgctxt "#([0-9]+)"$', block, flags=re.M)
        if not contexts:
            if _po_quoted_value(block, "msgid") == "":
                continue
            raise SystemExit("strings.po contains a block without a numeric msgctxt")
        if len(contexts) != 1:
            raise SystemExit(
                "strings.po entries must be separated by a blank line; "
                f"one block contains IDs: {', '.join(contexts)}"
            )
        msgid = _po_quoted_value(block, "msgid")
        if msgid is None:
            raise SystemExit(f"Language string #{contexts[0]} is missing a msgid")
        if not msgid:
            raise SystemExit(f"Language string #{contexts[0]} has an empty msgid")
        if _po_quoted_value(block, "msgstr") is None:
            raise SystemExit(f"Language string #{contexts[0]} is missing a msgstr")
        entries.append((int(contexts[0]), block))
    if not entries:
        raise SystemExit("strings.po contains no localised strings")
    return entries


def _po_ids(path):
    seen = set()
    duplicates = set()
    for string_id, _ in _po_entries(path):
        if string_id in seen:
            duplicates.add(string_id)
        else:
            seen.add(string_id)
    if duplicates:
        raise SystemExit(f"Duplicate language string IDs: {sorted(duplicates)}")
    return seen


def _setting_string_id(node, attribute):
    value = node.attrib.get(attribute, "").strip()
    if not value.isdigit() or int(value) < 30000:
        raise SystemExit(
            f"Settings {node.tag} '{node.attrib.get('id', '')}' must define a localised {attribute} ID"
        )
    return int(value)


def _validate_strings(addon, settings):
    ids = _po_ids(ROOT / "resources/language/resource.language.en_gb/strings.po")
    referenced = {int(action["label_id"]) for action in ACTION_REGISTRY}
    for node in list(addon.iter("label")) + list(settings.iter("heading")):
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
    files = [ROOT / "context.py", ROOT / "default.py", ROOT / "subtitles.py"]
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
