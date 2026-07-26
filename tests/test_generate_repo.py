import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile
from html.parser import HTMLParser
from pathlib import Path


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        values = dict(attrs)
        if values.get("href"):
            self.links.append(values["href"])


class GenerateRepoTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.zip_path = self.temp_dir / "managarr-addon_v1.2.3.zip"
        with zipfile.ZipFile(self.zip_path, "w") as archive:
            archive.writestr(
                "context.arr.manager/addon.xml",
                '<addon id="context.arr.manager" name="Kodi Managarr" version="1.2.3" provider-name="CB"><extension point="xbmc.addon.metadata"><assets><icon>resources/icon.png</icon><fanart>resources/fanart.jpg</fanart></assets></extension></addon>',
            )
            archive.writestr("context.arr.manager/LICENSE.txt", "GPL-3.0-or-later test licence")
            archive.writestr("context.arr.manager/resources/icon.png", b"fake-icon")
            archive.writestr("context.arr.manager/resources/fanart.jpg", b"fake-fanart")

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def run_generator(self, release_zip=None, out_name="pages", repo_version="1.0.0"):
        out_dir = self.temp_dir / out_name
        result = subprocess.run(
            [
                sys.executable,
                "scripts/generate_repo.py",
                str(release_zip or self.zip_path),
                "--out-dir",
                str(out_dir),
                "--repo-version",
                repo_version,
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        return result, out_dir

    def test_generate_repo_contract_and_archives(self):
        result, out_dir = self.run_generator()
        self.assertEqual(result.returncode, 0, result.stderr)
        addons_xml = out_dir / "addons.xml"
        root = ET.parse(addons_xml).getroot()
        self.assertEqual(
            [(item.attrib["id"], item.attrib["version"]) for item in root.findall("addon")],
            [("repository.managarr", "1.0.0"), ("context.arr.manager", "1.2.3")],
        )
        repository_addon = root.find("./addon[@id='repository.managarr']")
        self.assertEqual(repository_addon.findtext("./extension[@point='xbmc.addon.metadata']/license"), "GPL-3.0-or-later")
        self.assertEqual(
            repository_addon.findtext("./extension[@point='xbmc.addon.metadata']/website"),
            "https://cbkii.github.io/kodi-managarr",
        )
        directory = repository_addon.find("./extension[@point='xbmc.addon.repository']/dir")
        self.assertEqual(directory.findtext("hashes"), "sha256")
        for tag in ("info", "checksum", "datadir"):
            self.assertTrue(directory.findtext(tag).startswith("https://raw.githubusercontent.com/cbkii/kodi-managarr/gh-pages"))

        expected_md5 = hashlib.md5(addons_xml.read_bytes()).hexdigest()  # nosec B303: Kodi change token
        self.assertEqual((out_dir / "addons.xml.md5").read_text().strip(), expected_md5)
        self.assertTrue((out_dir / "addons.xml.sha256").is_file())
        self.assertTrue((out_dir / "context.arr.manager/resources/icon.png").is_file())
        self.assertTrue((out_dir / "context.arr.manager/resources/fanart.jpg").is_file())
        self.assertFalse((out_dir / "context.arr.manager/icon.png").exists())

        repository_zip = out_dir / "repository.managarr/repository.managarr-1.0.0.zip"
        repository_alias = out_dir / "repository.managarr/repository.managarr.zip"
        addon_zip = out_dir / "context.arr.manager/context.arr.manager-1.2.3.zip"
        addon_alias = out_dir / "context.arr.manager/context.arr.manager.zip"
        for archive_path in (repository_zip, repository_alias, addon_zip, addon_alias):
            self.assertTrue(archive_path.is_file())
            self.assertTrue(archive_path.with_name(archive_path.name + ".sha256").is_file())
            with zipfile.ZipFile(archive_path) as archive:
                self.assertIsNone(archive.testzip())
        self.assertEqual(repository_zip.read_bytes(), repository_alias.read_bytes())
        self.assertEqual(addon_zip.read_bytes(), addon_alias.read_bytes())
        with zipfile.ZipFile(repository_zip) as archive:
            self.assertNotIn(repository_zip.name, archive.namelist())
            self.assertNotIn(repository_alias.name, archive.namelist())
            self.assertIn("repository.managarr/addon.xml", archive.namelist())
            self.assertIn("repository.managarr/LICENSE.txt", archive.namelist())
        with zipfile.ZipFile(addon_zip) as archive:
            self.assertIn("context.arr.manager/addon.xml", archive.namelist())
            self.assertIn("context.arr.manager/LICENSE.txt", archive.namelist())

    def test_generated_site_links_to_installable_repository(self):
        result, out_dir = self.run_generator()
        self.assertEqual(result.returncode, 0, result.stderr)
        index = (out_dir / "index.html").read_text(encoding="utf-8")
        readme = (out_dir / "README.md").read_text(encoding="utf-8")
        self.assertIn("Kodi Managarr 1.2.3", index)
        self.assertIn("repository.managarr/repository.managarr.zip", index)
        self.assertIn("Kodi Managarr add-on repository", readme)
        self.assertIn("`1.2.3`", readme)
        self.assertIn("`1.0.0`", readme)
        self.assertIn("Re-publish an existing release", readme)
        self.assertNotIn("{{", index)
        self.assertNotIn("{{", readme)
        self.assertTrue((out_dir / "styles.css").is_file())
        self.assertTrue((out_dir / ".nojekyll").is_file())

        parser = LinkParser()
        parser.feed(index)
        local_links = [link for link in parser.links if not link.startswith(("https://", "http://", "mailto:"))]
        expected = {
            "addons.xml",
            "addons.xml.md5",
            "repository.managarr/repository.managarr.zip",
            "repository.managarr/repository.managarr.zip.sha256",
            "context.arr.manager/context.arr.manager.zip",
            "context.arr.manager/context.arr.manager.zip.sha256",
        }
        self.assertTrue(expected.issubset(set(local_links)))
        for link in local_links:
            self.assertTrue((out_dir / link).is_file(), link)

    def test_output_is_deterministic(self):
        old = os.environ.get("SOURCE_DATE_EPOCH")
        os.environ["SOURCE_DATE_EPOCH"] = "1700000000"
        try:
            first, first_dir = self.run_generator(out_name="first")
            second, second_dir = self.run_generator(out_name="second")
        finally:
            if old is None:
                os.environ.pop("SOURCE_DATE_EPOCH", None)
            else:
                os.environ["SOURCE_DATE_EPOCH"] = old
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 0, second.stderr)
        first_files = {p.relative_to(first_dir): p.read_bytes() for p in first_dir.rglob("*") if p.is_file()}
        second_files = {p.relative_to(second_dir): p.read_bytes() for p in second_dir.rglob("*") if p.is_file()}
        self.assertEqual(first_files, second_files)

    def test_rejects_wrong_root_missing_version_licence_traversal_and_bad_repo_version(self):
        cases = {
            "wrong-root": [
                ("other/addon.xml", '<addon id="context.arr.manager" version="1.0.0" />'),
                ("other/LICENSE.txt", "licence"),
            ],
            "missing-version": [
                ("context.arr.manager/addon.xml", '<addon id="context.arr.manager" />'),
                ("context.arr.manager/LICENSE.txt", "licence"),
            ],
            "missing-licence": [
                ("context.arr.manager/addon.xml", '<addon id="context.arr.manager" version="1.0.0" />'),
            ],
            "traversal": [
                ("context.arr.manager/addon.xml", '<addon id="context.arr.manager" version="1.0.0" />'),
                ("context.arr.manager/LICENSE.txt", "licence"),
                ("context.arr.manager/../escape.txt", "bad"),
            ],
        }
        for name, members in cases.items():
            with self.subTest(name=name):
                path = self.temp_dir / f"{name}.zip"
                with zipfile.ZipFile(path, "w") as archive:
                    for member, content in members:
                        archive.writestr(member, content)
                result, _ = self.run_generator(path, out_name=f"out-{name}")
                self.assertNotEqual(result.returncode, 0)

        result, _ = self.run_generator(repo_version="latest")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Repository add-on version must use x.y.z", result.stderr)


if __name__ == "__main__":
    unittest.main()
