import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "resources", "lib"))

from arr_manager.history import match_history, unique_history_matches
from arr_manager.models import HistoryMatch


class HistoryTests(unittest.TestCase):
    def test_matches_imported_path(self):
        file_record = {"id": 7, "relativePath": "Movie.2026.1080p-GROUP.mkv", "sceneName": "Movie.2026.1080p-GROUP"}
        records = [
            {
                "id": 99,
                "eventType": "downloadFolderImported",
                "sourceTitle": "Movie.2026.1080p-GROUP",
                "downloadId": "abc",
                "data": {"importedPath": "/movies/Movie/Movie.2026.1080p-GROUP.mkv"},
            }
        ]
        match = match_history(records, file_record)
        self.assertIsNotNone(match)
        self.assertEqual(match.history_id, 99)
        self.assertEqual(match.download_id, "abc")

    def test_rejects_weak_history_guess(self):
        file_record = {"id": 7, "relativePath": "Wanted.Release.mkv"}
        records = [{"id": 5, "sourceTitle": "Different.Release", "downloadId": "abc", "data": {}}]
        self.assertIsNone(match_history(records, file_record))

    def test_deduplicates_download_id(self):
        rows = [HistoryMatch(1, "x", "abc"), HistoryMatch(2, "x", "abc"), HistoryMatch(3, "y", "def")]
        self.assertEqual([row.history_id for row in unique_history_matches(rows)], [1, 3])


if __name__ == "__main__":
    unittest.main()
