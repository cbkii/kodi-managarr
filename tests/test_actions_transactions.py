import os
import sys
import unittest
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "resources", "lib"))

from arr_manager.actions import ArrManager
from arr_manager.errors import ApiError, SafetyError
from arr_manager.models import HistoryMatch, SelectedItem
from arr_manager.util import PathMapper


class Settings:
    backend = "api"
    confirm = False
    dry_run = False
    require_blocklist = True
    path_mapper = PathMapper([])
    poll_timeout = 1
    def validate_backend(self): return None


class UI:
    def __init__(self): self.synced = False
    def refresh_kodi_library(self): self.synced = True
    def wait_for_abort(self, seconds): return False


class Radarr:
    def __init__(self, fail_blocklist=False, search_result="successful"):
        self.calls = []
        self.fail_blocklist = fail_blocklist
        self.search_result = search_result
    def movie_files(self, movie_id):
        self.calls.append(("files", movie_id)); return [{"id": 7, "path": "/movies/Film/file.mkv"}]
    def movie_history(self, movie_id, event_type=3):
        self.calls.append(("history", movie_id, event_type)); return []
    def mark_history_failed(self, history_id):
        self.calls.append(("failed", history_id))
        if self.fail_blocklist: raise ApiError("blocklist failed")
    def delete_movie_file(self, file_id): self.calls.append(("delete", file_id))
    def search_movie(self, movie_id): self.calls.append(("search", movie_id)); return {"id": 99}
    def command_status(self, command_id):
        self.calls.append(("command", command_id))
        return {"id": command_id, "status": "completed", "result": self.search_result}


class TransactionTests(unittest.TestCase):
    def test_movie_replace_blocklists_before_delete_and_search(self):
        ui = UI(); manager = ArrManager(Settings(), ui, logger=None); manager._radarr = Radarr()
        selected = SelectedItem(media_type="movie", title="Film")
        match = HistoryMatch(history_id=42, source_title="Release", download_id="abc")
        with patch("arr_manager.actions_destructive.resolve_movie", return_value={"id": 3, "title": "Film"}), \
             patch("arr_manager.actions_destructive.match_history", return_value=match):
            result = manager._movie_replace(selected)
        self.assertIn("Blocklisted 1 matched release", result)
        self.assertEqual(manager._radarr.calls, [
            ("files", 3), ("history", 3, 3), ("failed", 42),
            ("delete", 7), ("search", 3), ("command", 99),
        ])
        self.assertTrue(ui.synced)

    def test_blocklist_failure_prevents_delete_and_search(self):
        manager = ArrManager(Settings(), UI(), logger=None); manager._radarr = Radarr(fail_blocklist=True)
        match = HistoryMatch(42, "Release", "abc")
        with patch("arr_manager.actions_destructive.resolve_movie", return_value={"id": 3, "title": "Film"}), \
             patch("arr_manager.actions_destructive.match_history", return_value=match):
            with self.assertRaises(SafetyError):
                manager._movie_replace(SelectedItem(media_type="movie", title="Film"))
        self.assertNotIn(("delete", 7), manager._radarr.calls)
        self.assertNotIn(("search", 3), manager._radarr.calls)

    def test_unsuccessful_search_reports_partial_commit(self):
        manager = ArrManager(Settings(), UI(), logger=None); manager._radarr = Radarr(search_result="unsuccessful")
        match = HistoryMatch(42, "Release", "abc")
        with patch("arr_manager.actions_destructive.resolve_movie", return_value={"id": 3, "title": "Film"}), \
             patch("arr_manager.actions_destructive.match_history", return_value=match):
            with self.assertRaisesRegex(SafetyError, "Partial operation"):
                manager._movie_replace(SelectedItem(media_type="movie", title="Film"))


if __name__ == "__main__":
    unittest.main()
