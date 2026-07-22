import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")


class ReleaseWorkflowTests(unittest.TestCase):
    def test_release_highlights_override_is_optional(self):
        match = re.search(
            r"(?ms)^\s{6}release_notes:\n(?P<body>(?:\s{8}.+\n)+)",
            WORKFLOW,
        )
        self.assertIsNotNone(match)
        body = match.group("body")
        self.assertIn("required: false", body)
        self.assertIn('default: ""', body)
        self.assertIn("blank uses the maintained addon.xml news", body)

    def test_blank_highlights_use_maintained_addon_metadata(self):
        self.assertIn(
            "notes = manual_notes or maintained_news or description or summary",
            WORKFLOW,
        )
        self.assertIn("RELEASE_HIGHLIGHTS: ${{ steps.metadata.outputs.release_notes }}", WORKFLOW)

    def test_kodi_news_is_shortened_without_truncating_release_highlights(self):
        self.assertIn("max_news_chars = 1500", WORKFLOW)
        self.assertIn("notes_for_addon = notes", WORKFLOW)
        self.assertIn("notes_for_addon[:available].rstrip() + '...'", WORKFLOW)
        self.assertIn("release_notes={notes}", WORKFLOW)

    def test_public_release_asset_uses_friendly_versioned_name(self):
        expected = "managarr-addon_v$VERSION.zip"
        self.assertIn(f'release_asset="dist/{expected}"', WORKFLOW)
        self.assertIn(f'sha256sum "{expected}" > "{expected}.sha256"', WORKFLOW)
        self.assertIn(f"Download \\`{expected}\\` from **Assets**", WORKFLOW)
        self.assertIn('with zipfile.ZipFile(f\'dist/managarr-addon_v{version}.zip\')', WORKFLOW)

    def test_kodi_archive_root_remains_the_addon_id(self):
        self.assertIn('internal_asset="dist/context.arr.manager-$VERSION.zip"', WORKFLOW)
        self.assertIn(
            "kodi-addon-checker --branch matrix dist/addon-check/context.arr.manager",
            WORKFLOW,
        )


if __name__ == "__main__":
    unittest.main()
