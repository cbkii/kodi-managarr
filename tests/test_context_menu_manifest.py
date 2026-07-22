import importlib.util
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIB_DIR = ROOT / "resources" / "lib"
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

from arr_manager.context_manifest import EXPECTED_CONTEXT_ACTIONS, ROOT_CONTEXT_LABEL  # noqa: E402


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

    def _branding_item(self):
        extension = self.addon.find("extension[@point='kodi.context.item']")
        self.assertIsNotNone(extension)
        root_menu = extension.find("menu[@id='kodi.core.main']")
        self.assertIsNotNone(root_menu)
        items = root_menu.findall("item")
        self.assertEqual(len(items), 1)
        return items[0]

    def test_single_runtime_root_item_is_registered(self):
        item = self._branding_item()
        self.assertEqual(item.attrib.get("library"), "context.py")
        self.assertEqual(item.attrib.get("args"), "menu")
        self.assertEqual(item.findtext("label").strip(), ROOT_CONTEXT_LABEL)
        self.assertEqual(EXPECTED_CONTEXT_ACTIONS, {"menu"})
        self.assertIn("ListItem.DBType(movie)", item.findtext("visible"))
        self.assertIn("ListItem.DBType(tvshow)", item.findtext("visible"))
        self.assertIn("ListItem.DBType(episode)", item.findtext("visible"))
        self.assertFalse(item.findall("menu"))

    def test_runtime_root_label_is_plain_ascii(self):
        label = self._branding_item().findtext("label").strip()
        self.assertTrue(label.isascii())
        self.assertEqual(label, "Managarr")


if __name__ == "__main__":
    unittest.main()
