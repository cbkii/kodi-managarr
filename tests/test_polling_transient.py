import os
import sys
import errno
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "resources", "lib"))

from arr_manager.actions import ArrManager
from arr_manager.errors import ApiError, SafetyError
from arr_manager.util import PathMapper

class Settings:
    poll_timeout = 3
    path_mapper = PathMapper([])

class UI:
    def __init__(self): self.waits = []
    def wait_for_abort(self, seconds):
        self.waits.append(seconds)
        return False

class Logger:
    def __init__(self): self.messages = []
    def warning(self, msg, *args): self.messages.append(msg % args)

class Radarr:
    def __init__(self): self.calls = 0
    def movie_files(self, movie_id):
        self.calls += 1
        if self.calls == 1:
            raise ApiError("temporary", status=503)
        return []

class SonarrPermanent:
    def episode_files(self, series_id):
        raise ApiError("auth", status=401)

class Client:
    def __init__(self, errors): self.errors = list(errors)
    def command_status(self, command_id):
        if self.errors:
            raise self.errors.pop(0)
        return {"id": command_id, "status": "completed"}

class PollingTransientTests(unittest.TestCase):
    def test_movie_file_poll_retries_transient_get(self):
        logger = Logger()
        manager = ArrManager(Settings(), UI(), logger)
        manager._radarr = Radarr()
        manager._wait_for_movie_file_removed(1, 9)
        self.assertEqual(manager._radarr.calls, 2)
        self.assertTrue(logger.messages)

    def test_episode_file_poll_does_not_retry_permanent_get(self):
        manager = ArrManager(Settings(), UI(), Logger())
        manager._sonarr = SonarrPermanent()
        with self.assertRaises(ApiError):
            manager._wait_for_episode_files_removed(1, {9})

    def test_command_poll_retries_transient_status(self):
        manager = ArrManager(Settings(), UI(), Logger())
        state = manager._poll_command(Client([ApiError("temporary", status=500)]), {"id": 5}, "rescan")
        self.assertEqual(state["status"], "completed")

    def test_command_poll_does_not_retry_permanent_status(self):
        manager = ArrManager(Settings(), UI(), Logger())
        with self.assertRaises(ApiError):
            manager._poll_command(Client([ApiError("forbidden", status=403)]), {"id": 5}, "rescan")

    def test_command_poll_retries_timeout_and_429(self):
        manager = ArrManager(Settings(), UI(), Logger())
        state = manager._poll_command(Client([TimeoutError("slow"), ApiError("rate", status=429)]), {"id": 5}, "rescan")
        self.assertEqual(state["status"], "completed")

    def test_command_poll_rejects_malformed_status_response(self):
        class BadClient:
            def command_status(self, command_id): return []
        manager = ArrManager(Settings(), UI(), Logger())
        with self.assertRaises(SafetyError):
            manager._poll_command(BadClient(), {"id": 5}, "rescan")

    def test_polling_does_not_retry_invalid_json_or_non_transient_oserror(self):
        manager = ArrManager(Settings(), UI(), Logger())
        self.assertFalse(manager._is_transient_poll_error(ApiError("API response contained invalid JSON")))
        self.assertFalse(manager._is_transient_poll_error(OSError(errno.EACCES, "denied")))
        self.assertTrue(manager._is_transient_poll_error(OSError(errno.ECONNRESET, "reset")))

    def test_search_queue_polls_to_completion_and_surfaces_failure(self):
        manager = ArrManager(Settings(), UI(), Logger())
        manager._queue_search(Client([]), {"id": 5}, "search")
        class FailedClient:
            def command_status(self, command_id): return {"id": command_id, "status": "failed", "message": "bad"}
        with self.assertRaises(SafetyError):
            manager._queue_search(FailedClient(), {"id": 6}, "search")

if __name__ == "__main__":
    unittest.main()
