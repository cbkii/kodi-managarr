import importlib.util
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_validator():
    spec = importlib.util.spec_from_file_location("managarr_validate", ROOT / "scripts/validate.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class LocalisationTests(unittest.TestCase):
    def test_po_messages_are_discrete_and_parseable(self):
        validator = load_validator()
        entries = validator._po_entries(
            ROOT / "resources/language/resource.language.en_gb/strings.po"
        )
        self.assertGreater(len(entries), 100)
        self.assertEqual(len(entries), len({string_id for string_id, _ in entries}))

    def test_every_visible_setting_has_label_and_help_copy(self):
        validator = load_validator()
        ids = validator._po_ids(
            ROOT / "resources/language/resource.language.en_gb/strings.po"
        )
        settings = ET.parse(ROOT / "resources/settings.xml").getroot()
        for node in settings.findall(".//category") + settings.findall(".//setting"):
            with self.subTest(tag=node.tag, setting_id=node.attrib.get("id")):
                for attribute in ("label", "help"):
                    value = node.attrib.get(attribute, "")
                    self.assertTrue(value.isdigit(), (node.attrib.get("id"), attribute, value))
                    self.assertIn(int(value), ids)


if __name__ == "__main__":
    unittest.main()
