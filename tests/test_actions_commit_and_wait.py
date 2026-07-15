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
    def __init__(self):
        self.path_mapper = PathMapper([])
        self.protected_paths = []
    def validate_backend(self): return None


class UI:
    def __init__(self):
        self.waits = []
        self.synced = []
    def wait_for_abort(self, seconds):
        self.waits.append(seconds)
        return False
    def refresh_kodi_library(self): self.synced.append("refresh")
    def sync_deleted_episodes(self, selected, linked=None): self.synced.append(("episodes", selected.db_id))


class Backend:
    name = "Kodi VFS (SMB/SFTP)"
    def __init__(self): self.deleted = []
    def delete_file(self, path): self.deleted.append(path)
    def close(self): pass


class Sonarr:
    def __init__(self):
        self.updated = []
        self.deleted_files = []
        self.command_statuses = [{"id": 5, "status": "failed", "message": "boom"}]
    def update_episode(self, episode): self.updated.append(dict(episode))
    def delete_episode_file(self, file_id): self.deleted_files.append(file_id)
    def rescan_series(self, series_id): return {"id": 5}
    def command_status(self, command_id): return self.command_statuses.pop(0)
    def episode_files(self, series_id): return [{"id": 9, "path": "smb://pi/Shows/file.mkv"}]


class CommitAndWaitTests(unittest.TestCase):
    def test_bounded_wait_uses_kodi_waiter_without_fallback_delay(self):
        ui = UI()
        manager = ArrManager(Settings(), ui, logger=None)
        with patch("threading.Event.wait") as fallback:
            manager._bounded_wait(0.25)
        self.assertEqual(ui.waits, [0.25])
        fallback.assert_not_called()

    def test_bounded_wait_shutdown_raises(self):
        ui = UI()
        ui.wait_for_abort = lambda seconds: True
        manager = ArrManager(Settings(), ui, logger=None)
        with self.assertRaises(SafetyError):
            manager._bounded_wait(0.1)

    def test_episode_exclude_does_not_restore_monitoring_after_direct_delete_commits_then_rescan_fails(self):
        ui = UI()
        backend = Backend()
        manager = ArrManager(Settings(), ui, logger=None)
        manager._sonarr = Sonarr()
        selected = SelectedItem(media_type="episode", tvshow_title="Show", season=1, episode=2, db_id=77)
        linked = [{"id": 1, "seasonNumber": 1, "episodeNumber": 2, "episodeFileId": 9, "monitored": True}]
        file_record = {"id": 9, "path": "smb://pi/Shows/file.mkv"}
        with patch("arr_manager.actions.resolve_series", return_value={"id": 3, "title": "Show", "path": "/shows/Show"}), \
             patch("arr_manager.actions.resolve_episode_context", return_value=(linked[0], linked, file_record)), \
             patch("arr_manager.actions.make_direct_backend", return_value=backend):
            with self.assertRaises(SafetyError):
                manager._episode_exclude(selected)
        self.assertEqual(backend.deleted, ["smb://pi/Shows/file.mkv"])
        self.assertEqual(len(manager._sonarr.updated), 1)
        self.assertFalse(manager._sonarr.updated[0]["monitored"])


if __name__ == "__main__":
    unittest.main()
