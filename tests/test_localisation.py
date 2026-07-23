import importlib.util
import tempfile
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
    def setUp(self):
        self.validator = load_validator()

    def _write_po(self, content, newline=None):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        path = Path(temporary.name) / "strings.po"
        with path.open("w", encoding="utf-8", newline=newline) as handle:
            handle.write(content)
        return path

    def test_po_messages_are_discrete_and_parseable(self):
        entries = self.validator._po_entries(
            ROOT / "resources/language/resource.language.en_gb/strings.po"
        )
        self.assertGreater(len(entries), 100)
        self.assertEqual(len(entries), len({string_id for string_id, _ in entries}))

    def test_po_parser_accepts_wrapped_msgid_and_comment_only_block(self):
        path = self._write_po(
            '# Translator note\n\n'
            'msgid ""\n'
            'msgstr ""\n'
            '"Language: en_GB\\n"\n\n'
            '#. setting help\n'
            'msgctxt "#32120"\n'
            'msgid ""\n'
            '"Configure safety checks "\n'
            '"and shared network behaviour."\n'
            'msgstr ""\n'
            '"Configure safety checks "\n'
            '"and shared network behaviour."\n'
        )
        entries = self.validator._po_entries(path)
        self.assertEqual([string_id for string_id, _ in entries], [32120])

    def test_po_parser_rejects_adjacent_entries_without_blank_line(self):
        path = self._write_po(
            'msgctxt "#32100"\n'
            'msgid "General"\n'
            'msgstr "General"\n'
            'msgctxt "#32101"\n'
            'msgid "Deletion backend"\n'
            'msgstr "Deletion backend"\n'
        )
        with self.assertRaisesRegex(SystemExit, "must be separated by a blank line"):
            self.validator._po_entries(path)

    def test_po_duplicate_detection_is_strict(self):
        path = self._write_po(
            'msgctxt "#32100"\n'
            'msgid "General"\n'
            'msgstr "General"\n\n'
            'msgctxt "#32100"\n'
            'msgid "General duplicate"\n'
            'msgstr "General duplicate"\n'
        )
        with self.assertRaisesRegex(SystemExit, "Duplicate language string IDs"):
            self.validator._po_ids(path)

    def test_po_parser_rejects_crlf_source(self):
        path = self._write_po(
            'msgctxt "#32100"\nmsgid "General"\nmsgstr "General"\n',
            newline="\r\n",
        )
        with self.assertRaisesRegex(SystemExit, "Unix line endings"):
            self.validator._po_entries(path)

    def test_every_visible_setting_has_label_and_help_copy(self):
        ids = self.validator._po_ids(
            ROOT / "resources/language/resource.language.en_gb/strings.po"
        )
        settings = ET.parse(ROOT / "resources/settings.xml").getroot()
        for node in settings.findall(".//category") + settings.findall(".//setting"):
            with self.subTest(tag=node.tag, setting_id=node.attrib.get("id")):
                for attribute in ("label", "help"):
                    value = node.attrib.get(attribute, "")
                    self.assertTrue(value.isdigit(), (node.attrib.get("id"), attribute, value))
                    self.assertIn(int(value), ids)

    def test_every_settings_heading_has_localised_copy(self):
        ids = self.validator._po_ids(
            ROOT / "resources/language/resource.language.en_gb/strings.po"
        )
        settings = ET.parse(ROOT / "resources/settings.xml").getroot()
        headings = list(settings.iter("heading"))
        self.assertTrue(headings)
        for heading in headings:
            with self.subTest(heading=heading.text):
                value = (heading.text or "").strip()
                self.assertTrue(value.isdigit(), value)
                self.assertIn(int(value), ids)


if __name__ == "__main__":
    unittest.main()
