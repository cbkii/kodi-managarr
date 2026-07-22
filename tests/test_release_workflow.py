import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RELEASE_WORKFLOW = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
PAGES_WORKFLOW = (ROOT / ".github" / "workflows" / "pages.yml").read_text(encoding="utf-8")


class ReleaseWorkflowTests(unittest.TestCase):
    def test_release_highlights_override_is_optional(self):
        match = re.search(
            r"(?ms)^\s{6}release_notes:\n(?P<body>(?:\s{8}.+\n)+)",
            RELEASE_WORKFLOW,
        )
        self.assertIsNotNone(match)
        body = match.group("body")
        self.assertIn("required: false", body)
        self.assertIn('default: ""', body)
        self.assertIn("blank uses the maintained addon.xml news", body)

    def test_blank_highlights_use_maintained_addon_metadata(self):
        self.assertIn(
            "notes = manual_notes or maintained_news or description or summary",
            RELEASE_WORKFLOW,
        )
        self.assertIn("RELEASE_HIGHLIGHTS: ${{ steps.metadata.outputs.release_notes }}", RELEASE_WORKFLOW)

    def test_kodi_news_is_shortened_without_truncating_release_highlights(self):
        self.assertIn("max_news_chars = 1500", RELEASE_WORKFLOW)
        self.assertIn("notes_for_addon = notes", RELEASE_WORKFLOW)
        self.assertIn("notes_for_addon[:available].rstrip() + '...'", RELEASE_WORKFLOW)
        self.assertIn("release_notes={notes}", RELEASE_WORKFLOW)

    def test_public_release_asset_uses_friendly_versioned_name(self):
        expected = "managarr-addon_v$VERSION.zip"
        self.assertIn(f'release_asset="dist/{expected}"', RELEASE_WORKFLOW)
        self.assertIn(f'sha256sum "{expected}" > "{expected}.sha256"', RELEASE_WORKFLOW)
        self.assertIn(f"Download \`{expected}\` from **Assets**", RELEASE_WORKFLOW)
        self.assertIn("with zipfile.ZipFile(f'dist/managarr-addon_v{version}.zip')", RELEASE_WORKFLOW)

    def test_kodi_archive_root_remains_the_addon_id(self):
        self.assertIn('internal_asset="dist/context.arr.manager-$VERSION.zip"', RELEASE_WORKFLOW)
        self.assertIn(
            "kodi-addon-checker --branch matrix dist/addon-check/context.arr.manager",
            RELEASE_WORKFLOW,
        )


class RepositoryPagesWorkflowTests(unittest.TestCase):
    def test_repository_publication_is_stable_only(self):
        self.assertIn("github.event.release.prerelease == false", PAGES_WORKFLOW)
        self.assertIn("github.event.release.draft == false", PAGES_WORKFLOW)
        self.assertIn("--exclude-drafts --exclude-pre-releases", PAGES_WORKFLOW)
        self.assertIn("test \"$(jq -r '.isDraft'", PAGES_WORKFLOW)
        self.assertIn("test \"$(jq -r '.isPrerelease'", PAGES_WORKFLOW)

    def test_exact_release_tag_and_single_asset_are_used(self):
        self.assertIn('EVENT_TAG: ${{ github.event.release.tag_name }}', PAGES_WORKFLOW)
        self.assertIn('gh release view "$tag"', PAGES_WORKFLOW)
        self.assertIn('gh release download "$RELEASE_TAG"', PAGES_WORKFLOW)
        self.assertIn('test "${#assets[@]}" -eq 1', PAGES_WORKFLOW)
        self.assertNotIn("fetch-gh-release-asset", PAGES_WORKFLOW)

    def test_repository_generation_is_validated_before_upload(self):
        self.assertIn("export SOURCE_DATE_EPOCH=1700000000", PAGES_WORKFLOW)
        self.assertIn("python scripts/generate_repo.py release.zip", PAGES_WORKFLOW)
        self.assertIn("assert archive.testzip() is None", PAGES_WORKFLOW)
        self.assertIn("actions/upload-pages-artifact", PAGES_WORKFLOW)
        self.assertIn("actions/deploy-pages", PAGES_WORKFLOW)


if __name__ == "__main__":
    unittest.main()
