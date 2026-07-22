import os
import sys
import unittest
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "resources", "lib"))

from arr_manager.actions import ArrManager
from arr_manager.errors import SafetyError
from arr_manager.models import SelectedItem
from arr_manager.util import PathMapper


class Settings:
    backend = "vfs"
    confirm = False
    dry_run = False
    require_blocklist = False
    poll_timeout = 1
    path_mapper = PathMapper([("/shows/Show", "smb://pi/Shows/Show")])
    protected_paths = ["smb://pi/Shows/Show"]
    def validate_backend(self): return None


class UI:
    def __init__(self, approved=True): self.waits = []; self.confirmations = []; self.approved = approved
    def wait_for_abort(self, seconds): self.waits.append(seconds); return False
    def confirm(self, heading, message): self.confirmations.append((heading, message)); return self.approved
    def sync_deleted_episodes(self, selected, linked=None): return None


class Backend:
    name = "Kodi VFS"
    def __init__(self): self.deleted = []; self.preflighted = []
    def preflight_file(self, path): self.preflighted.append(path)
    def delete_file(self, path): self.deleted.append(path)
    def close(self): pass


class Sonarr:
    def __init__(self): self.updated = []
    def update_episode(self, episode): self.updated.append(dict(episode)); return episode
    def rescan_series(self, series_id): return {"id": 5}
    def command_status(self, command_id): return {"id": command_id, "status": "failed", "result": "unsuccessful", "message": "boom"}
    def episode_files(self, series_id): return [{"id": 9, "path": "/shows/Show/file.mkv"}]


class CommitAndWaitTests(unittest.TestCase):
    def test_bounded_wait_uses_kodi_waiter(self):
        ui = UI(); manager = ArrManager(Settings(), ui, logger=None)
        with patch("threading.Event.wait") as fallback: manager._bounded_wait(0.25)
        self.assertEqual(ui.waits, [0.25]); fallback.assert_not_called()

    def test_vfs_requires_confirmation_even_when_setting_disabled(self):
        ui = UI(approved=False); backend = Backend(); manager = ArrManager(Settings(), ui, logger=None); manager._sonarr = Sonarr()
        linked = [{"id": 1, "seasonNumber": 1, "episodeNumber": 2, "episodeFileId": 9, "monitored": True}]
        with patch("arr_manager.actions_destructive.resolve_series", return_value={"id": 3, "title": "Show", "path": "/shows/Show"}), \
             patch("arr_manager.actions_destructive.resolve_episode_context", return_value=(linked[0], linked, {"id": 9, "path": "/shows/Show/file.mkv"})), \
             patch("arr_manager.actions_shared.make_direct_backend", return_value=backend):
            result = manager._episode_exclude(SelectedItem(media_type="episode", tvshow_title="Show", season=1, episode=2))
        self.assertEqual(result, "Cancelled")
        self.assertTrue(ui.confirmations)
        self.assertEqual(backend.deleted, [])

    def test_post_delete_rescan_failure_keeps_unmonitored_and_reports_partial_commit(self):
        ui = UI(); backend = Backend(); manager = ArrManager(Settings(), ui, logger=None); manager._sonarr = Sonarr()
        linked = [{"id": 1, "seasonNumber": 1, "episodeNumber": 2, "episodeFileId": 9, "monitored": True}]
        with patch("arr_manager.actions_destructive.resolve_series", return_value={"id": 3, "title": "Show", "path": "/shows/Show"}), \
             patch("arr_manager.actions_destructive.resolve_episode_context", return_value=(linked[0], linked, {"id": 9, "path": "/shows/Show/file.mkv"})), \
             patch("arr_manager.actions_shared.make_direct_backend", return_value=backend):
            with self.assertRaisesRegex(SafetyError, "Partial operation"):
                manager._episode_exclude(SelectedItem(media_type="episode", tvshow_title="Show", season=1, episode=2))
        self.assertEqual(backend.deleted, ["smb://pi/Shows/Show/file.mkv"])
        self.assertEqual(len(manager._sonarr.updated), 1)
        self.assertFalse(manager._sonarr.updated[0]["monitored"])


if __name__ == "__main__":
    unittest.main()
