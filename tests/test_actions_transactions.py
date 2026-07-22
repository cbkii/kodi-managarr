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

class TestCloseProgress(unittest.TestCase):
    def test_close_progress_success(self):
        ui = UI()
        manager = ArrManager(Settings(), ui, logger=None)
        class Dialog:
            closed = False
            def close(self):
                self.closed = True
        dialog = Dialog()
        manager._close_progress(dialog)
        self.assertTrue(dialog.closed)

    def test_close_progress_exception_logged(self):
        ui = UI()
        class FakeLogger:
            exceptions = []
            def exception(self, msg):
                self.exceptions.append(msg)
        logger = FakeLogger()
        manager = ArrManager(Settings(), ui, logger=logger)
        class Dialog:
            def close(self):
                raise ValueError("Boom")
        dialog = Dialog()
        manager._close_progress(dialog)
        self.assertEqual(logger.exceptions, ["Could not close progress dialog"])

    def test_close_progress_exception_suppressed_no_logger(self):
        ui = UI()
        manager = ArrManager(Settings(), ui, logger=None)
        class Dialog:
            def close(self):
                raise ValueError("Boom")
        dialog = Dialog()
        manager._close_progress(dialog)
        # Should not raise

class TestEpisodeExcludeMonitoring(unittest.TestCase):
    def setUp(self):
        self.ui = UI()
        self.settings = Settings()
        self.settings.backend = "api"
        class Sonarr:
            def __init__(self):
                self.calls = []
            def delete_episode_file(self, *args):
                self.calls.append(("delete_episode_file", args))
            def set_episodes_monitored(self, ids, monitored):
                self.calls.append(("set_episodes_monitored", ids, monitored))
        self.sonarr = Sonarr()
        self.manager = ArrManager(self.settings, self.ui, logger=None)
        self.manager._sonarr = self.sonarr

    @patch("arr_manager.actions_destructive.resolve_series", return_value={"id": 1, "title": "Series"})
    @patch("arr_manager.actions_destructive.resolve_episode_context", return_value=(None, [{"id": 10, "monitored": True}, {"id": 11, "monitored": False}], {"id": 99}))
    @patch("arr_manager.actions.ArrManager._approved", return_value=True)
    def test_mixed_monitoring_sends_one_bulk_request(self, mock_approve, mock_resolve, mock_series):
        selected = SelectedItem(media_type="episode")
        self.manager._episode_exclude(selected)
        self.assertEqual(self.sonarr.calls, [
            ("set_episodes_monitored", [10], False),
            ("delete_episode_file", (99,))
        ])

    @patch("arr_manager.actions_destructive.resolve_series", return_value={"id": 1, "title": "Series"})
    @patch("arr_manager.actions_destructive.resolve_episode_context", return_value=(None, [{"id": 10, "monitored": False}, {"id": 11, "monitored": False}], {"id": 99}))
    @patch("arr_manager.actions.ArrManager._approved", return_value=True)
    def test_all_unmonitored_sends_no_monitoring_request(self, mock_approve, mock_resolve, mock_series):
        selected = SelectedItem(media_type="episode")
        self.manager._episode_exclude(selected)
        self.assertEqual(self.sonarr.calls, [
            ("delete_episode_file", (99,))
        ])

    @patch("arr_manager.actions_destructive.resolve_series", return_value={"id": 1, "title": "Series"})
    @patch("arr_manager.actions_destructive.resolve_episode_context", return_value=(None, [{"id": 10, "monitored": True}, {"id": 11, "monitored": True}], {"id": 99}))
    @patch("arr_manager.actions.ArrManager._approved", return_value=True)
    def test_failed_delete_restores_monitoring(self, mock_approve, mock_resolve, mock_series):
        class SonarrForRestoration:
            def __init__(self):
                self.calls = []
            def set_episodes_monitored(self, ids, monitored):
                self.calls.append(("set_episodes_monitored", ids, monitored))
            def delete_episode_file(self, *args):
                self.calls.append(("delete_episode_file", args))

        self.manager._sonarr = SonarrForRestoration()

        # Inject failure right before committed=True
        original_mark = self.manager._record_transaction # this is wrong, tx.mark is on TransactionState
        # Let's just mock TransactionState.mark
        with patch("arr_manager.actions_destructive.TransactionState.mark", side_effect=ValueError("Failed before commit")):
            selected = SelectedItem(media_type="episode")
            with self.assertRaises(SafetyError):
                self.manager._episode_exclude(selected)

        self.assertEqual(self.manager._sonarr.calls, [
            ("set_episodes_monitored", [10, 11], False),
            ("set_episodes_monitored", [10, 11], True),
        ])


    @patch("arr_manager.actions_destructive.resolve_series", return_value={"id": 1, "title": "Series"})
    @patch("arr_manager.actions_destructive.resolve_episode_context", return_value=(None, [{"id": 10, "monitored": True}, {"id": 11, "monitored": True}], {"id": 99}))
    @patch("arr_manager.actions.ArrManager._approved", return_value=True)
    def test_failed_delete_after_commit_boundary_does_not_restore_monitoring(self, mock_approve, mock_resolve, mock_series):
        class SonarrForPostCommit:
            def __init__(self):
                self.calls = []
            def set_episodes_monitored(self, ids, monitored):
                self.calls.append(("set_episodes_monitored", ids, monitored))
            def delete_episode_file(self, *args):
                self.calls.append(("delete_episode_file", args))
                raise ValueError("API error after commit boundary")

        self.manager._sonarr = SonarrForPostCommit()
        selected = SelectedItem(media_type="episode")

        with self.assertRaises(SafetyError):
            self.manager._episode_exclude(selected)

        self.assertEqual(self.manager._sonarr.calls, [
            ("set_episodes_monitored", [10, 11], False),
            ("delete_episode_file", (99,)),
        ])

class TestSeriesReplace(unittest.TestCase):
    def setUp(self):
        self.ui = UI()
        self.settings = Settings()
        self.settings.backend = "api"

        class Sonarr:
            def __init__(self):
                self.calls = []
            def episode_files(self, *args):
                return [{"id": 1, "path": "/media/S01E01.mkv"}]
            def episodes(self, *args):
                return [{"id": 101, "episodeFileId": 1}]
            def series_history(self, *args, **kwargs):
                return []
            def delete_episode_files(self, *args):
                self.calls.append(("delete_episode_files", args))
            def search_series(self, *args):
                return {"id": 88}
            def mark_history_failed(self, *args):
                pass

        self.sonarr = Sonarr()
        self.manager = ArrManager(self.settings, self.ui, logger=None)
        self.manager._sonarr = self.sonarr

    @patch("arr_manager.actions_destructive.resolve_series", return_value={"id": 1, "title": "Series"})
    @patch("arr_manager.actions_destructive.match_history", return_value=HistoryMatch(history_id=1, source_title="Release", download_id="abc"))
    @patch("arr_manager.actions.ArrManager._approved", return_value=True)
    @patch("arr_manager.actions_destructive.make_direct_backend", return_value=None)
    @patch("arr_manager.actions.ArrManager._queue_search")
    def test_series_replace_api_success(self, mock_queue, mock_backend, mock_approve, mock_match, mock_resolve):
        self.settings.require_blocklist = False
        selected = SelectedItem(media_type="tvshow")
        result = self.manager._series_replace(selected)
        self.assertEqual(self.sonarr.calls[0][0], "delete_episode_files")
        self.assertTrue(mock_queue.called)

    @patch("arr_manager.actions_destructive.resolve_series", return_value={"id": 1, "title": "Series"})
    @patch("arr_manager.actions_destructive.match_history", return_value=HistoryMatch(history_id=1, source_title="Release", download_id="abc"))
    @patch("arr_manager.actions.ArrManager._approved", return_value=True)
    @patch("arr_manager.actions_destructive.make_direct_backend", return_value=None)
    def test_series_replace_dry_run(self, mock_backend, mock_approve, mock_match, mock_resolve):
        self.settings.dry_run = True
        selected = SelectedItem(media_type="tvshow")
        result = self.manager._series_replace(selected)
        self.assertEqual(self.sonarr.calls, [])

    @patch("arr_manager.actions_destructive.resolve_series", return_value={"id": 1, "title": "Series"})
    @patch("arr_manager.actions_destructive.match_history", return_value=None)
    def test_series_replace_strict_history_missing(self, mock_match, mock_resolve):
        self.settings.require_blocklist = True
        selected = SelectedItem(media_type="tvshow")
        from arr_manager.errors import BlocklistError
        with self.assertRaises(BlocklistError):
            self.manager._series_replace(selected)


    @patch("arr_manager.actions_destructive.resolve_series", return_value={"id": 1, "title": "Series"})
    @patch("arr_manager.actions_destructive.match_history", return_value=HistoryMatch(history_id=1, source_title="Release", download_id="abc"))
    @patch("arr_manager.actions.ArrManager._approved", return_value=False)
    @patch("arr_manager.actions_destructive.make_direct_backend", return_value=None)
    def test_series_replace_user_cancellation(self, mock_backend, mock_approve, mock_match, mock_resolve):
        self.settings.require_blocklist = False
        selected = SelectedItem(media_type="tvshow")
        result = self.manager._series_replace(selected)
        self.assertEqual(result, self.manager._m("cancelled"))
        self.assertEqual(self.sonarr.calls, [])

    @patch("arr_manager.actions_destructive.resolve_series", return_value={"id": 1, "title": "Series"})
    @patch("arr_manager.actions_destructive.match_history", return_value=HistoryMatch(history_id=1, source_title="Release", download_id="abc"))
    @patch("arr_manager.actions.ArrManager._approved", return_value=True)
    def test_series_replace_duplicate_direct_targets_rejected(self, mock_approve, mock_match, mock_resolve):
        self.settings.require_blocklist = False
        selected = SelectedItem(media_type="tvshow")

        class FakeBackend:
            def preflight_file(self, path): pass
            def close(self): pass
            def delete_file(self, path): pass

        with patch("arr_manager.actions_destructive.make_direct_backend", return_value=FakeBackend()), \
             patch("arr_manager.actions.ArrManager._backend_path", return_value="/media/target.mkv"), \
             patch("arr_manager.actions.ArrManager._remote_file_path", return_value="/media/remote.mkv"):

             # Need Sonarr to return multiple files that map to the exact same backend path
             self.sonarr.episode_files = lambda *args: [{"id": 1, "path": "/1.mkv"}, {"id": 2, "path": "/2.mkv"}]
             with self.assertRaises(SafetyError) as ctx:
                 self.manager._series_replace(selected)
             self.assertIn("Multiple Sonarr file records resolved to the same direct-delete target", str(ctx.exception))


    @patch("arr_manager.actions_destructive.resolve_series", return_value={"id": 1, "title": "Series"})
    @patch("arr_manager.actions_destructive.match_history", return_value=HistoryMatch(history_id=1, source_title="Release", download_id="abc"))
    @patch("arr_manager.actions.ArrManager._approved", return_value=True)
    def test_series_replace_transaction_recording_on_failure(self, mock_approve, mock_match, mock_resolve):
        self.settings.require_blocklist = False
        selected = SelectedItem(media_type="tvshow")

        class FakeBackend:
            def preflight_file(self, path): pass
            def close(self): pass
            def delete_file(self, path): pass

        class MockSonarr(self.sonarr.__class__):
            def delete_episode_files(self, *args):
                raise ValueError("API error during delete")

        self.manager._sonarr = MockSonarr()

        with patch("arr_manager.actions_destructive.make_direct_backend", return_value=FakeBackend()), \
             patch("arr_manager.actions.ArrManager._backend_path", return_value="/media/target.mkv"), \
             patch("arr_manager.actions.ArrManager._remote_file_path", return_value="/media/remote.mkv"), \
             patch("arr_manager.actions.ArrManager._record_transaction") as mock_record:

             with self.assertRaises(SafetyError) as ctx:
                 self.manager._series_replace(selected)

             self.assertIn("episode file deletion", str(ctx.exception))
             self.assertTrue(mock_record.called)
