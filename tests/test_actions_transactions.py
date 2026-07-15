import os
import sys
import unittest
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "resources", "lib"))

from arr_manager.actions import ArrManager
from arr_manager.errors import ApiError
from arr_manager.history import HistoryMatch
from arr_manager.models import SelectedItem
from arr_manager.util import PathMapper


class Settings:
    backend = "api"
    confirm = False
    dry_run = False
    require_blocklist = True
    path_mapper = PathMapper([])
    poll_timeout = 1
    def validate_backend(self):
        return None


class UI:
    def __init__(self):
        self.refreshed = False
    def refresh_kodi_library(self):
        self.refreshed = True
    def wait_for_abort(self, seconds):
        return False


class Radarr:
    def __init__(self, fail_blocklist=False):
        self.calls = []
        self.fail_blocklist = fail_blocklist
    def movie_files(self, movie_id):
        self.calls.append(("files", movie_id))
        return [{"id": 7, "path": "/movies/Film/file.mkv"}]
    def movie_history(self, movie_id, event_type=3):
        self.calls.append(("history", movie_id, event_type))
        return []
    def mark_history_failed(self, history_id):
        self.calls.append(("failed", history_id))
        if self.fail_blocklist:
            raise ApiError("blocklist failed")
    def delete_movie_file(self, file_id):
        self.calls.append(("delete", file_id))
    def search_movie(self, movie_id):
        self.calls.append(("search", movie_id))
        return {"id": 99}


class TransactionTests(unittest.TestCase):
    def test_movie_replace_blocklists_before_delete_and_search(self):
        ui = UI()
        manager = ArrManager(Settings(), ui, logger=None)
        manager._radarr = Radarr()
        selected = SelectedItem(media_type="movie", title="Film")
        match = HistoryMatch(history_id=42, source_title="Release", download_id="abc")
        with patch("arr_manager.actions.resolve_movie", return_value={"id": 3, "title": "Film"}), \
             patch("arr_manager.actions.match_history", return_value=match):
            result = manager._movie_replace(selected)
        self.assertIn("Blocklisted, deleted", result)
        self.assertEqual(manager._radarr.calls, [
            ("files", 3), ("history", 3, 3), ("failed", 42), ("delete", 7), ("search", 3)
        ])
        self.assertTrue(ui.refreshed)

    def test_movie_replace_does_not_delete_when_blocklist_fails(self):
        manager = ArrManager(Settings(), UI(), logger=None)
        manager._radarr = Radarr(fail_blocklist=True)
        selected = SelectedItem(media_type="movie", title="Film")
        match = HistoryMatch(history_id=42, source_title="Release", download_id="abc")
        with patch("arr_manager.actions.resolve_movie", return_value={"id": 3, "title": "Film"}), \
             patch("arr_manager.actions.match_history", return_value=match):
            with self.assertRaises(ApiError):
                manager._movie_replace(selected)
        self.assertNotIn(("delete", 7), manager._radarr.calls)
        self.assertNotIn(("search", 3), manager._radarr.calls)


if __name__ == "__main__":
    unittest.main()
