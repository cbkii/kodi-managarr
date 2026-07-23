import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "resources", "lib"))

from arr_manager.localization import render_strings_po, runtime_catalog


HEADER = '''# Kodi Media Center language file
msgid ""
msgstr ""
"Project-Id-Version: Kodi Managarr\\n"
"Language: en_GB\\n"
"Content-Type: text/plain; charset=UTF-8\\n"
'''


class LocalizationTests(unittest.TestCase):
    def test_render_adds_every_runtime_string_and_is_idempotent(self):
        rendered = render_strings_po(HEADER)
        for string_id in runtime_catalog():
            self.assertIn(f'msgctxt "#{string_id}"', rendered)
        self.assertEqual(render_strings_po(rendered), rendered)

    def test_existing_runtime_string_must_match_its_fallback(self):
        string_id, (_, fallback) = next(iter(sorted(runtime_catalog().items())))
        source = HEADER + f'''\nmsgctxt "#{string_id}"
msgid "wrong"
msgstr "wrong"
'''
        with self.assertRaisesRegex(ValueError, "does not match runtime fallback"):
            render_strings_po(source)
        self.assertNotEqual(fallback, "wrong")

    def test_duplicate_source_ids_are_rejected(self):
        source = HEADER + '''
msgctxt "#39999"
msgid "One"
msgstr "One"

msgctxt "#39999"
msgid "Two"
msgstr "Two"
'''
        with self.assertRaisesRegex(ValueError, "Duplicate language string ID"):
            render_strings_po(source)


if __name__ == "__main__":
    unittest.main()
