import importlib.util
import unicodedata
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXPECTED_ACTIONS = {
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


def load_validator():
    spec = importlib.util.spec_from_file_location("managarr_validate", ROOT / "scripts/validate.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ContextMenuManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.addon = ET.parse(ROOT / "addon.xml").getroot()
        cls.validator = load_validator()
        cls.po_ids = cls.validator._po_ids(
            ROOT / "resources/language/resource.language.en_gb/strings.po"
        )

    def _context_extension(self):
        extension = self.addon.find("extension[@point='kodi.context.item']")
        self.assertIsNotNone(extension)
        return extension

    def test_complete_submenu_tree_is_registered(self):
        extension = self._context_extension()
        root_menu = extension.find("menu[@id='kodi.core.main']")
        self.assertIsNotNone(root_menu)

        branding_menus = root_menu.findall("menu")
        self.assertEqual(len(branding_menus), 1)
        branding_menu = branding_menus[0]

        label = (branding_menu.findtext("label") or "").strip()
        self.assertEqual(label, "Managarr")
        self.assertFalse(any(unicodedata.category(character) == "So" for character in label))
        self.assertNotIn("\ufe0f", label)

        actions = set()
        for item in branding_menu.findall(".//item"):
            self.assertEqual(item.attrib.get("library"), "context.py")
            action = item.attrib.get("args", "")
            self.assertTrue(action)
            self.assertNotIn(action, actions)
            actions.add(action)
            self.assertTrue((item.findtext("visible") or "").strip())

        self.assertEqual(actions, EXPECTED_ACTIONS)

        nested = branding_menu.findall("menu")
        self.assertEqual(len(nested), 2)
        for submenu in nested:
            with self.subTest(label=submenu.findtext("label")):
                self.assertTrue(submenu.findall("item"))

    def test_every_numeric_context_label_is_localised(self):
        extension = self._context_extension()
        for label in extension.findall(".//label"):
            value = (label.text or "").strip()
            if not value.isdigit():
                continue
            with self.subTest(label=value):
                self.assertIn(int(value), self.po_ids)


if __name__ == "__main__":
    unittest.main()
