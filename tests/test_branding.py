import os
import unittest
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class BrandingTests(unittest.TestCase):
    def test_addon_metadata_uses_kodi_managarr_branding_and_action_list(self):
        root = ET.parse(os.path.join(ROOT, "addon.xml")).getroot()
        self.assertEqual(root.attrib["name"], "Kodi Managarr")

        metadata = root.find("extension[@point='xbmc.addon.metadata']")
        self.assertIsNotNone(metadata)
        summary = metadata.findtext("summary", default="")
        description = metadata.findtext("description", default="")
        self.assertEqual(summary, "Manage Radarr and Sonarr media from Kodi.")
        self.assertIn("Actions:\n• Delete & Exclude\n• Delete & Replace", description)

    def test_context_menu_uses_requested_managarr_label(self):
        path = os.path.join(
            ROOT,
            "resources",
            "language",
            "resource.language.en_gb",
            "strings.po",
        )
        with open(path, encoding="utf-8") as handle:
            content = handle.read()
        self.assertIn('msgid "🗑️ Managarr"', content)
        self.assertNotIn('msgid "Managarr"', content)

    def test_legacy_user_facing_name_is_absent(self):
        paths = [
            "README.md",
            "addon.xml",
            "docs/ARCHITECTURE.md",
            ".github/workflows/release.yml",
            "resources/language/resource.language.en_gb/strings.po",
            "resources/lib/arr_manager/__init__.py",
            "resources/lib/arr_manager/kodi.py",
        ]
        for relative_path in paths:
            with self.subTest(path=relative_path):
                path = os.path.join(ROOT, *relative_path.split("/"))
                with open(path, encoding="utf-8") as handle:
                    self.assertNotIn("Arr Manager", handle.read())


if __name__ == "__main__":
    unittest.main()
