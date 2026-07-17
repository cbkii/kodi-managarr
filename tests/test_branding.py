import os
import unittest
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class BrandingTests(unittest.TestCase):
    def test_metadata_uses_publication_assets_and_full_scope(self):
        root = ET.parse(os.path.join(ROOT, "addon.xml")).getroot()
        self.assertEqual(root.attrib["id"], "context.arr.manager")
        self.assertEqual(root.attrib["name"], "Kodi Managarr")
        self.assertEqual(root.attrib["version"], "0.2.0")
        metadata = root.find("extension[@point='xbmc.addon.metadata']")
        self.assertEqual(metadata.findtext("license"), "GPL-3.0-or-later")
        self.assertEqual(metadata.findtext("assets/icon"), "resources/icon.png")
        self.assertEqual(metadata.findtext("assets/fanart"), "resources/fanart.jpg")
        args = {
            item.attrib["args"]
            for item in root.findall(".//extension[@point='kodi.context.item']//item")
        }
        self.assertEqual(args, {
            "status", "search_now", "monitor", "unmonitor",
            "change_quality_profile", "queue_view", "queue_remove",
            "delete_exclude", "delete_replace",
        })

    def test_legacy_branding_is_absent_from_runtime_metadata(self):
        for relative in (
            "addon.xml",
            "resources/language/resource.language.en_gb/strings.po",
            "resources/lib/arr_manager/kodi.py",
        ):
            with self.subTest(path=relative):
                with open(os.path.join(ROOT, *relative.split("/")), encoding="utf-8") as handle:
                    self.assertNotIn("Arr Manager", handle.read())


if __name__ == "__main__":
    unittest.main()
