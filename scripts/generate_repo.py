#!/usr/bin/env python3
"""
Deterministically generate a Kodi repository structure from a released Managarr zip.
"""
import argparse
import hashlib
import os
import shutil
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

def create_addon_xml(repo_version, addon_version, repo_url):
    root = ET.Element("addon", id="repository.managarr", name="Kodi Managarr Repository", version=repo_version, provider_name="CB")

    requires = ET.SubElement(root, "requires")
    ET.SubElement(requires, "import", addon="xbmc.addon", version="19.0.0")

    extension_repo = ET.SubElement(root, "extension", point="xbmc.addon.repository", name="Kodi Managarr Repository")
    dir_node = ET.SubElement(extension_repo, "dir")
    ET.SubElement(dir_node, "info", compressed="false").text = f"{repo_url}/addons.xml"
    ET.SubElement(dir_node, "checksum").text = f"{repo_url}/addons.xml.md5"
    ET.SubElement(dir_node, "datadir", zip="true").text = f"{repo_url}/"

    extension_meta = ET.SubElement(root, "extension", point="xbmc.addon.metadata")
    ET.SubElement(extension_meta, "summary", lang="en_GB").text = "Official repository for Kodi Managarr."
    ET.SubElement(extension_meta, "description", lang="en_GB").text = "Provides automatic updates for Kodi Managarr."
    ET.SubElement(extension_meta, "platform").text = "all"

    assets = ET.SubElement(extension_meta, "assets")
    ET.SubElement(assets, "icon").text = "icon.png"

    return ET.tostring(root, encoding="utf-8", xml_declaration=True).decode("utf-8")

def _deterministic_zip(out_path, source_dir, epoch):
    import stat
    import time
    from datetime import datetime, timezone

    if epoch < 315532800:
        epoch = 315532800

    dt = datetime.fromtimestamp(epoch, timezone.utc)
    ts = (dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second // 2 * 2)

    with zipfile.ZipFile(out_path, "w") as zf:
        for root, _, files in os.walk(source_dir):
            for file in sorted(files):
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, source_dir.parent)

                info = zipfile.ZipInfo(rel_path, ts)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.create_system = 3
                info.flag_bits |= 0x800
                info.external_attr = ((stat.S_IFREG | 0o644) & 0xFFFF) << 16

                with open(full_path, "rb") as f:
                    zf.writestr(info, f.read(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("release_zip", type=Path)
    parser.add_argument("--repo-version", default="1.0.0")
    parser.add_argument("--repo-url", default="https://cbkii.github.io/kodi-managarr")
    parser.add_argument("--out-dir", type=Path, default=Path("pages_output"))
    args = parser.parse_args()

    if not args.release_zip.is_file():
        raise FileNotFoundError(f"Missing release zip: {args.release_zip}")

    out_dir = args.out_dir
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    # 1. Extract addon.xml from the release zip to find its version
    addon_version = "unknown"
    with zipfile.ZipFile(args.release_zip, "r") as zf:
        for name in zf.namelist():
            if name.endswith("addon.xml") and name.startswith("context.arr.manager/"):
                addon_xml_content = zf.read(name)
                root = ET.fromstring(addon_xml_content)
                addon_version = root.attrib.get("version")
                break

    if addon_version == "unknown":
        raise ValueError("Could not find addon.xml in the release zip")

    # 2. Copy the release zip to canonical path
    addon_dir = out_dir / "context.arr.manager"
    addon_dir.mkdir()

    canonical_zip_path = addon_dir / f"context.arr.manager-{addon_version}.zip"
    shutil.copy2(args.release_zip, canonical_zip_path)

    # 3. Extract metadata beside the zip (addon.xml, icon, fanart)
    with zipfile.ZipFile(args.release_zip, "r") as zf:
        zf.extract("context.arr.manager/addon.xml", out_dir)
        try:
            zf.extract("context.arr.manager/resources/icon.png", out_dir)
            shutil.copy2(out_dir / "context.arr.manager/resources/icon.png", addon_dir / "icon.png")
        except KeyError:
            pass
        try:
            zf.extract("context.arr.manager/resources/fanart.jpg", out_dir)
            shutil.copy2(out_dir / "context.arr.manager/resources/fanart.jpg", addon_dir / "fanart.jpg")
        except KeyError:
            pass
    shutil.rmtree(out_dir / "context.arr.manager/resources", ignore_errors=True)

    # 4. Generate repository.managarr structure
    repo_dir = out_dir / "repository.managarr"
    repo_dir.mkdir()
    repo_xml_content = create_addon_xml(args.repo_version, addon_version, args.repo_url)

    with open(repo_dir / "addon.xml", "w") as f:
        f.write(repo_xml_content)

    # Provide a basic icon for the repo (copy from main addon if it exists)
    if (addon_dir / "icon.png").exists():
        shutil.copy2(addon_dir / "icon.png", repo_dir / "icon.png")

    # Package the repository addon zip deterministically
    repo_zip_path = repo_dir / f"repository.managarr-{args.repo_version}.zip"
    epoch = int(os.environ.get("SOURCE_DATE_EPOCH", 1700000000))
    _deterministic_zip(repo_zip_path, repo_dir, epoch)

    # Generate index for Pages (optional but good)
    with open(out_dir / "index.html", "w") as f:
        f.write("<html><body><h1>Kodi Managarr Repository</h1></body></html>")

    # 5. Generate addons.xml
    addons_root = ET.Element("addons")
    # Add repo addon info
    repo_addon = ET.fromstring(repo_xml_content)
    addons_root.append(repo_addon)
    # Add main addon info
    main_addon = ET.fromstring(addon_xml_content)
    addons_root.append(main_addon)

    addons_xml = ET.tostring(addons_root, encoding="utf-8", xml_declaration=True).decode("utf-8")
    with open(out_dir / "addons.xml", "w") as f:
        f.write(addons_xml)

    # 6. Generate addons.xml.md5
    md5 = hashlib.md5(addons_xml.encode("utf-8")).hexdigest()
    with open(out_dir / "addons.xml.md5", "w") as f:
        f.write(md5)

    print("Repository generated successfully.")

if __name__ == "__main__":
    main()
