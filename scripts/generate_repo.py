#!/usr/bin/env python3
"""Deterministically build the Managarr Kodi repository from a release ZIP."""

import argparse
import hashlib
import os
import shutil
import stat
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

ADDON_ID = "context.arr.manager"
REPOSITORY_ID = "repository.managarr"
DEFAULT_REPOSITORY_URL = "https://cbkii.github.io/kodi-managarr"
DEFAULT_EPOCH = 1700000000


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_text(path, value):
    path.write_text(value, encoding="utf-8", newline="\n")


def _safe_member_name(name):
    if not name or "\\" in name:
        return False
    path = PurePosixPath(name)
    return not path.is_absolute() and ".." not in path.parts


def _validate_release_zip(path):
    if not path.is_file() or not zipfile.is_zipfile(path):
        raise ValueError(f"Release asset is not a valid ZIP: {path}")
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise ValueError("Release ZIP failed integrity validation")
        names = archive.namelist()
        if not names:
            raise ValueError("Release ZIP is empty")
        for info in archive.infolist():
            if not _safe_member_name(info.filename):
                raise ValueError(f"Unsafe release ZIP member: {info.filename}")
            mode = (info.external_attr >> 16) & 0xFFFF
            if stat.S_ISLNK(mode):
                raise ValueError(f"Symlink is not permitted in release ZIP: {info.filename}")
            if PurePosixPath(info.filename).parts[0] != ADDON_ID:
                raise ValueError("Release ZIP must contain exactly one context.arr.manager root")

        manifest_name = f"{ADDON_ID}/addon.xml"
        licence_name = f"{ADDON_ID}/LICENSE.txt"
        if names.count(manifest_name) != 1:
            raise ValueError("Release ZIP must contain exactly one context.arr.manager/addon.xml")
        if names.count(licence_name) != 1:
            raise ValueError("Release ZIP must contain exactly one context.arr.manager/LICENSE.txt")
        manifest_bytes = archive.read(manifest_name)
        try:
            manifest = ET.fromstring(manifest_bytes)
        except ET.ParseError as exc:
            raise ValueError("Release addon.xml is malformed") from exc
        if manifest.tag != "addon" or manifest.attrib.get("id") != ADDON_ID:
            raise ValueError("Release addon.xml has the wrong add-on ID")
        version = (manifest.attrib.get("version") or "").strip()
        if not version:
            raise ValueError("Release addon.xml is missing a version")

        metadata = {"addon.xml": manifest_bytes, "LICENSE.txt": archive.read(licence_name)}
        for relative in ("resources/icon.png", "resources/fanart.jpg"):
            source = f"{ADDON_ID}/{relative}"
            if source in names:
                metadata[relative] = archive.read(source)
        return version, manifest, metadata


def create_repository_manifest(repo_version, repo_url):
    repo_url = repo_url.rstrip("/")
    root = ET.Element(
        "addon", id=REPOSITORY_ID, name="Kodi Managarr Repository",
        version=repo_version, **{"provider-name": "CB"},
    )
    requires = ET.SubElement(root, "requires")
    ET.SubElement(requires, "import", addon="xbmc.addon", version="19.0.0")
    repository = ET.SubElement(root, "extension", point="xbmc.addon.repository", name="Kodi Managarr Repository")
    directory = ET.SubElement(repository, "dir", minversion="19.0.0")
    ET.SubElement(directory, "info", compressed="false").text = f"{repo_url}/addons.xml"
    ET.SubElement(directory, "checksum").text = f"{repo_url}/addons.xml.md5"
    ET.SubElement(directory, "datadir", zip="true").text = f"{repo_url}/"
    ET.SubElement(directory, "hashes").text = "sha256"

    metadata = ET.SubElement(root, "extension", point="xbmc.addon.metadata")
    ET.SubElement(metadata, "summary", lang="en_GB").text = "Repository for Kodi Managarr"
    ET.SubElement(metadata, "description", lang="en_GB").text = "Install Kodi Managarr and receive normal Kodi add-on updates."
    ET.SubElement(metadata, "platform").text = "all"
    ET.SubElement(metadata, "license").text = "GPL-3.0-or-later"
    ET.SubElement(metadata, "website").text = repo_url
    ET.SubElement(metadata, "source").text = "https://github.com/cbkii/kodi-managarr"
    assets = ET.SubElement(metadata, "assets")
    ET.SubElement(assets, "icon").text = "icon.png"
    ET.SubElement(assets, "fanart").text = "fanart.jpg"
    return root


def _xml_bytes(element):
    return ET.tostring(element, encoding="utf-8", xml_declaration=True)


def _deterministic_zip(out_path, source_dir, epoch):
    epoch = max(int(epoch), 315532800)
    timestamp = datetime.fromtimestamp(epoch, timezone.utc)
    zip_time = (timestamp.year, timestamp.month, timestamp.day, timestamp.hour, timestamp.minute, timestamp.second // 2 * 2)
    source_dir = source_dir.resolve()
    out_path = out_path.resolve()
    if out_path == source_dir or source_dir in out_path.parents:
        raise ValueError("Repository ZIP output must be outside the directory being archived")
    with zipfile.ZipFile(out_path, "w") as archive:
        for path in sorted(path for path in source_dir.rglob("*") if path.is_file()):
            if path.is_symlink():
                raise ValueError(f"Symlink is not permitted in repository package: {path}")
            info = zipfile.ZipInfo(path.relative_to(source_dir.parent).as_posix(), zip_time)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.flag_bits |= 0x800
            info.external_attr = ((stat.S_IFREG | 0o644) & 0xFFFF) << 16
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def _write_hash(path):
    _write_text(path.with_name(path.name + ".sha256"), f"{_sha256(path)}  {path.name}\n")


def _write_relative(root, relative, content):
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)


def generate_repository(release_zip, out_dir, repo_version, repo_url, epoch):
    addon_version, addon_manifest, metadata = _validate_release_zip(release_zip)
    repo_version = str(repo_version or "").strip()
    if not repo_version:
        raise ValueError("Repository add-on version is required")
    if not str(repo_url).lower().startswith("https://"):
        raise ValueError("Repository URL must use HTTPS")

    out_dir = out_dir.resolve()
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    addon_dir = out_dir / ADDON_ID
    addon_dir.mkdir()
    canonical_zip = addon_dir / f"{ADDON_ID}-{addon_version}.zip"
    shutil.copyfile(release_zip, canonical_zip)
    _write_hash(canonical_zip)
    _write_relative(addon_dir, "addon.xml", metadata["addon.xml"])
    for relative in ("resources/icon.png", "resources/fanart.jpg"):
        if relative in metadata:
            _write_relative(addon_dir, relative, metadata[relative])

    repository_dir = out_dir / REPOSITORY_ID
    repository_dir.mkdir()
    repository_manifest = create_repository_manifest(repo_version, repo_url)
    _write_relative(repository_dir, "addon.xml", _xml_bytes(repository_manifest))
    _write_relative(repository_dir, "LICENSE.txt", metadata["LICENSE.txt"])
    if "resources/icon.png" in metadata:
        _write_relative(repository_dir, "icon.png", metadata["resources/icon.png"])
    if "resources/fanart.jpg" in metadata:
        _write_relative(repository_dir, "fanart.jpg", metadata["resources/fanart.jpg"])

    repository_zip = repository_dir / f"{REPOSITORY_ID}-{repo_version}.zip"
    temporary_zip = out_dir / f".{repository_zip.name}.tmp"
    _deterministic_zip(temporary_zip, repository_dir, epoch)
    os.replace(temporary_zip, repository_zip)
    _write_hash(repository_zip)

    addons = ET.Element("addons")
    addons.append(repository_manifest)
    addons.append(addon_manifest)
    addons_bytes = _xml_bytes(addons)
    (out_dir / "addons.xml").write_bytes(addons_bytes)
    _write_text(out_dir / "addons.xml.md5", hashlib.md5(addons_bytes).hexdigest() + "\n")  # nosec B303: Kodi change token
    _write_text(out_dir / "addons.xml.sha256", hashlib.sha256(addons_bytes).hexdigest() + "\n")
    _write_text(out_dir / "index.html", "<!doctype html><meta charset=\"utf-8\"><title>Kodi Managarr Repository</title><h1>Kodi Managarr Repository</h1>\n")

    with zipfile.ZipFile(repository_zip) as archive:
        if archive.testzip() is not None or repository_zip.name in archive.namelist():
            raise ValueError("Generated repository add-on ZIP failed validation")
        if not {f"{REPOSITORY_ID}/addon.xml", f"{REPOSITORY_ID}/LICENSE.txt"}.issubset(archive.namelist()):
            raise ValueError("Generated repository add-on ZIP is missing required files")
    return addon_version, repository_zip


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("release_zip", type=Path)
    parser.add_argument("--repo-version", default="1.0.0")
    parser.add_argument("--repo-url", default=DEFAULT_REPOSITORY_URL)
    parser.add_argument("--out-dir", type=Path, default=Path("pages_output"))
    args = parser.parse_args()
    epoch = int(os.environ.get("SOURCE_DATE_EPOCH", DEFAULT_EPOCH))
    addon_version, repository_zip = generate_repository(args.release_zip, args.out_dir, args.repo_version, args.repo_url, epoch)
    print(f"Repository generated for {ADDON_ID} {addon_version}: {repository_zip}")


if __name__ == "__main__":
    main()
