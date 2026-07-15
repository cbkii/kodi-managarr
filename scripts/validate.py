#!/usr/bin/env python3
import compileall
import os
import re
import sys
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    for relative in ("addon.xml", "resources/settings.xml"):
        ET.parse(os.path.join(ROOT, relative))
        print(f"OK XML: {relative}")
    if not compileall.compile_dir(ROOT, quiet=1, rx=re.compile(r"[\\/]\.git[\\/]")):
        print("Python compilation failed", file=sys.stderr)
        return 1
    print("OK Python compilation")
    required = [
        "addon.xml",
        "context.py",
        "default.py",
        "resources/icon.png",
        "resources/settings.xml",
        "resources/language/resource.language.en_gb/strings.po",
    ]
    missing = [path for path in required if not os.path.exists(os.path.join(ROOT, path))]
    if missing:
        print("Missing required files: " + ", ".join(missing), file=sys.stderr)
        return 1
    print("OK required files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
