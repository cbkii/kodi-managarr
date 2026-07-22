import unittest
from unittest.mock import patch, MagicMock

from arr_manager.retention.executor import RetentionExecutor
from arr_manager.retention.models import RetentionCandidate
from arr_manager.errors import SafetyError, ApiError

class TestRetentionExecutor(unittest.TestCase):
    def setUp(self):
        self.arr_manager = MagicMock()
        self.kodi = MagicMock()
        self.ui = MagicMock()
        self.enumerator = MagicMock()
        self.logger = MagicMock()
        self.executor = RetentionExecutor(self.arr_manager, self.kodi, self.ui, self.enumerator, self.logger)

        self.movie_cand = RetentionCandidate("movie", 1, 10, 100, "Film", "Film", True, 0, 0, {})
        self.episode_cand = RetentionCandidate("episode", 2, 20, 200, "Ep", "Ep", True, 0, 0, {}, season=1, episode=1, file_path="/ep.mkv")

    def test_revalidate_movie_success(self):
        self.kodi.call.return_value = {"moviedetails": {"title": "Film"}}
        self.enumerator._process_kodi_movie.return_value = RetentionCandidate("movie", 1, 10, 100, "Film", "Film", True, 0, 0, {})

        fresh = self.executor.revalidate_candidate(self.movie_cand)
        self.assertEqual(fresh.arr_id, 10)

    def test_revalidate_movie_identity_changed(self):
        self.kodi.call.return_value = {"moviedetails": {"title": "Film"}}
        self.enumerator._process_kodi_movie.return_value = RetentionCandidate("movie", 1, 99, 100, "Film", "Film", True, 0, 0, {})

        with self.assertRaisesRegex(SafetyError, "identity changed"):
            self.executor.revalidate_candidate(self.movie_cand)

    def test_revalidate_movie_watched_changed(self):
        self.kodi.call.return_value = {"moviedetails": {"title": "Film"}}
        self.enumerator._process_kodi_movie.return_value = RetentionCandidate("movie", 1, 10, 100, "Film", "Film", False, 0, 0, {})

        with self.assertRaisesRegex(SafetyError, "watched state changed"):
            self.executor.revalidate_candidate(self.movie_cand)

    def test_revalidate_not_found(self):
        self.kodi.call.return_value = {}
        with self.assertRaisesRegex(SafetyError, "not found in Kodi"):
            self.executor.revalidate_candidate(self.movie_cand)

    def test_execute_dry_run(self):
        report = self.executor.execute_deletion(self.movie_cand, dry_run=True)
        self.assertEqual(report.action_taken, "dry_run")
        self.kodi.call.assert_not_called()

    @patch('arr_manager.retention.executor.RetentionExecutor.revalidate_candidate')
    def test_execute_movie_success(self, mock_revalidate):
        mock_revalidate.return_value = self.movie_cand

        report = self.executor.execute_deletion(self.movie_cand, dry_run=False)
        self.assertEqual(report.action_taken, "deleted")
        self.arr_manager.radarr.delete_movie.assert_called_once_with(10, delete_files=True, add_exclusion=True)
        self.arr_manager._sync_kodi.assert_called_once()

    @patch('arr_manager.retention.executor.RetentionExecutor.revalidate_candidate')
    @patch('arr_manager.resolver.resolve_series')
    @patch('arr_manager.resolver.resolve_episode_context')
    def test_execute_episode_success(self, mock_resolve_context, mock_resolve_series, mock_revalidate):
        mock_revalidate.return_value = self.episode_cand
        mock_resolve_series.return_value = {"id": 20}

        ep1 = {"id": 1, "monitored": True}
        ep2 = {"id": 2, "monitored": False}
        mock_resolve_context.return_value = (None, [ep1, ep2], {"id": 200})

        report = self.executor.execute_deletion(self.episode_cand, dry_run=False)
        self.assertEqual(report.action_taken, "deleted")

        # Verify unmonitor
        self.arr_manager.sonarr.update_episode.assert_called_once_with({"id": 1, "monitored": False})

        # Verify delete file
        self.arr_manager.sonarr.delete_episode_file.assert_called_once_with(200)

    @patch('arr_manager.retention.executor.RetentionExecutor.revalidate_candidate')
    @patch('arr_manager.resolver.resolve_series')
    @patch('arr_manager.resolver.resolve_episode_context')
    def test_execute_episode_rollback(self, mock_resolve_context, mock_resolve_series, mock_revalidate):
        mock_revalidate.return_value = self.episode_cand
        mock_resolve_series.return_value = {"id": 20}

        ep1 = {"id": 1, "monitored": True}
        mock_resolve_context.return_value = (None, [ep1], {"id": 200})

        self.arr_manager.sonarr.delete_episode_file.side_effect = ApiError("Delete failed")

        report = self.executor.execute_deletion(self.episode_cand, dry_run=False)
        self.assertEqual(report.action_taken, "failed")
        self.assertIn("Delete failed", report.error_message)

        # Verify rollback
        self.assertEqual(self.arr_manager.sonarr.update_episode.call_count, 2)
        self.arr_manager.sonarr.update_episode.assert_any_call({"id": 1, "monitored": False})
        self.arr_manager.sonarr.update_episode.assert_any_call({"id": 1, "monitored": True})

if __name__ == "__main__":
    unittest.main()
