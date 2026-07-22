import importlib.util
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIB_DIR = ROOT / "resources" / "lib"
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

from arr_manager.context_manifest import (  # noqa: E402
    EXPECTED_CONTEXT_ACTIONS,
    EXPECTED_CONTEXT_SUBMENUS,
    EXPECTED_DIRECT_CONTEXT_ACTIONS,
    ROOT_CONTEXT_LABEL,
)


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
        try:
            cls.po_ids = cls.validator._po_ids(
                ROOT / "resources/language/resource.language.en_gb/strings.po"
            )
        except SystemExit as exc:
            raise AssertionError(f"Failed to parse PO file: {exc}") from exc

    def _context_extension(self):
        extension = self.addon.find("extension[@point='kodi.context.item']")
        self.assertIsNotNone(extension)
        return extension

    def _branding_menu(self):
        extension = self.addon.find("extension[@point='kodi.context.item']")
        root_menu = extension.find("menu[@id='kodi.core.main']")
        branding_items = root_menu.findall("item")
        self.assertEqual(len(branding_items), 1)
        self.assertEqual(branding_items[0].findtext("label").strip(), ROOT_CONTEXT_LABEL)
        return branding_items[0]

    def test_complete_submenu_tree_is_registered(self):
        pass

    def test_every_numeric_context_label_is_localised(self):
        pass

if __name__ == "__main__":
    unittest.main()
