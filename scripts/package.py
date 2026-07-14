#!/usr/bin/env python3
import os
import zipfile
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARENT = os.path.dirname(ROOT)
VERSION = ET.parse(os.path.join(ROOT, "addon.xml")).getroot().attrib["version"]
OUTPUT = os.path.join(PARENT, f"context.arr.manager-{VERSION}.zip")
EXCLUDED_DIRS = {".git", "__pycache__", ".pytest_cache", ".idea", ".vscode"}

with zipfile.ZipFile(OUTPUT, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
    for current, dirs, files in os.walk(ROOT):
        dirs[:] = [name for name in dirs if name not in EXCLUDED_DIRS]
        for name in files:
            if name.endswith((".pyc", ".pyo", ".zip")):
                continue
            source = os.path.join(current, name)
            relative = os.path.relpath(source, os.path.dirname(ROOT))
            archive.write(source, relative)
print(OUTPUT)
