import os
import sys
import tempfile
import time
import unittest
from unittest import mock

from arr_manager.retention.models import RetentionCandidate, RetentionReportItem, RetentionScanResult
from arr_manager.retention.reports import RetentionStateStore
from arr_manager.retention.service import RetentionService
from arr_manager.retention.service_daemon import run_service


class Addon:
    def __init__(self, values=None, profile=""):
        self.values = dict(values or {})
        self.profile = profile
    def getSetting(self, key): return self.values.get(key, "")
    def setSetting(self, key, value): self.values[key] = value
    def getAddonInfo(self, key):
        return {"profile": self.profile, "version": "1.2.0", "name": "Kodi Managarr"}.get(key, "")
    def getLocalizedString(self, _string_id): return ""


class FullSettings:
    def __init__(self, addon):
        self.addon = addon
        self.dry_run = False
        self.pin_invalid = False
        self.pin_enabled = False
        self.pin_hash = b""
        self.pin_salt = b""
        self.path_mapper = object()


class Manager:
    def __init__(self, addon): self.settings = FullSettings(addon)


class UI:
    def __init__(self):
        self.notifications = []
        self.modal_calls = []
        self.jsonrpc = object()
    def notification(self, message, **kwargs): self.notifications.append((message, kwargs))
    def ok(self, *args): self.modal_calls.append(("ok", args))
    def text(self, *args): self.modal_calls.append(("text", args))
    def confirm(self, *args): self.modal_calls.append(("confirm", args)); return True
    def progress(self, *args): self.modal_calls.append(("progress", args)); return mock.MagicMock()


class Store:
    def __init__(self): self.state = {"schema": 1}; self.report = {}; self.locked = False
    def load_state(self): return dict(self.state)
    def save_state(self, state): self.state = dict(state)
    def load_report(self): return dict(self.report)
    def save_report(self, report): self.report = dict(report)
    def acquire_lock(self, stale_after_seconds=0):
        if self.locked: return False
        self.locked = True; return True
    def release_lock(self): self.locked = False


class RetentionSettings:
    enabled = True
    include_movies = True
    include_episodes = False
    watched_only = True
    use_added_age = True
    added_age_days = 0
    use_watched_age = True
    watched_age_days = 0
    criteria_mode = "all"
    periodic_enabled = True
    interval_hours = 1
    max_deletions = 2
    background_dry_run = True
    notification_mode = "errors_only"


class Enumerator:
    def __init__(self, candidates): self.candidates = list(candidates)
    def iter_scan_results(self, _settings):
        for item in self.candidates:
            yield RetentionScanResult(candidate=item)


class Executor:
    def __init__(self): self.calls = []
    def execute(self, candidate, settings, dry_run=False, can_continue=None):
        self.calls.append((candidate.stable_key, dry_run))
        return RetentionReportItem(
            media_type=candidate.media_type,
            display_name=candidate.display_name,
            stable_key=candidate.stable_key,
            kodi_db_ids=list(candidate.kodi_db_ids),
            arr_id=candidate.arr_id,
            file_id=candidate.file_id,
            eligible=True,
            reason="eligible",
            action_taken="dry_run" if dry_run else "deleted",
            committed=not dry_run,
            stages=[] if dry_run else ["deleted"],
        )


def movie(index):
    now = time.time()
    return RetentionCandidate(
        media_type="movie", kodi_db_ids=(index,), arr_id=index, file_id=index + 100,
        title=f"Movie {index}", display_name=f"Movie {index}", watched=True,
        last_played=now - 86400, date_added=now - 86400,
    )


class StateStoreTests(unittest.TestCase):
    def test_lock_is_exclusive_and_stale_lock_recovers(self):
        with tempfile.TemporaryDirectory() as directory:
            addon = Addon(profile=directory)
            fake_vfs = mock.MagicMock()
            fake_vfs.translatePath.return_value = directory
            with mock.patch.dict(sys.modules, {"xbmcvfs": fake_vfs}):
                store = RetentionStateStore(addon)
            self.assertTrue(store.acquire_lock())
            self.assertFalse(store.acquire_lock())
            old = time.time() - 7200
            os.utime(store.lock_file, (old, old))
            self.assertTrue(store.acquire_lock(stale_after_seconds=3600))
            store.release_lock()
            self.assertFalse(os.path.exists(store.lock_file))

    def test_stale_owner_cannot_release_replacement_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            addon = Addon(profile=directory)
            fake_vfs = mock.MagicMock(); fake_vfs.translatePath.return_value = directory
            with mock.patch.dict(sys.modules, {"xbmcvfs": fake_vfs}):
                first = RetentionStateStore(addon)
                second = RetentionStateStore(addon)
            self.assertTrue(first.acquire_lock())
            old = time.time() - 7200
            os.utime(first.lock_file, (old, old))
            self.assertTrue(second.acquire_lock(stale_after_seconds=3600))
            first.release_lock()
            self.assertTrue(os.path.exists(second.lock_file))
            second.release_lock()
            self.assertFalse(os.path.exists(second.lock_file))

    def test_reports_are_bounded_and_processed_state_is_pruned(self):
        with tempfile.TemporaryDirectory() as directory:
            addon = Addon(profile=directory)
            fake_vfs = mock.MagicMock(); fake_vfs.translatePath.return_value = directory
            with mock.patch.dict(sys.modules, {"xbmcvfs": fake_vfs}):
                store = RetentionStateStore(addon)
            now = time.time()
            store.save_state({"recent_processed": [
                {"key": f"movie:{i}", "time": now} for i in range(250)
            ] + [{"key": "expired", "time": now - 40 * 86400}]})
            self.assertLessEqual(len(store.load_state()["recent_processed"]), 200)
            store.save_report({"items": [{"display_name": str(i)} for i in range(150)]})
            self.assertEqual(len(store.load_report()["items"]), 100)


class RetentionServiceTests(unittest.TestCase):
    def build(self, *, dry_run=True, periodic=True, candidates=()):
        addon = Addon({
            "retention_enabled": "true",
            "retention_periodic_enabled": "true" if periodic else "false",
        })
        manager = Manager(addon)
        ui = UI(); store = Store(); service = RetentionService(manager, object(), ui, mock.MagicMock(), store)
        settings = RetentionSettings()
        settings.background_dry_run = dry_run
        settings.periodic_enabled = periodic
        enumerator = Enumerator(candidates)
        executor = Executor()
        service._components = mock.MagicMock(return_value=(settings, enumerator, executor))
        return service, addon, manager, ui, store, settings, executor

    def test_real_periodic_enable_requires_authorization(self):
        service, _addon, _manager, _ui, _store, _settings, _executor = self.build(dry_run=False)
        with self.assertRaisesRegex(Exception, "not authorised"):
            service.enable_periodic(authorized=False)
        service.enable_periodic(authorized=True)

    def test_background_dry_run_obeys_batch_limit_and_uses_no_modal_ui(self):
        service, _addon, _manager, ui, store, _settings, executor = self.build(
            dry_run=True, candidates=[movie(1), movie(2), movie(3)]
        )
        store.state["next_due"] = 0
        result = service.run_background()
        self.assertEqual(result["status"], "completed")
        self.assertEqual(len(executor.calls), 2)
        self.assertTrue(all(dry_run for _key, dry_run in executor.calls))
        self.assertEqual(ui.modal_calls, [])
        self.assertTrue(store.report)

    def test_not_due_and_disabled_do_not_scan(self):
        service, _addon, _manager, _ui, store, settings, executor = self.build(candidates=[movie(1)])
        store.state["next_due"] = time.time() + 3600
        self.assertEqual(service.run_background()["status"], "not_due")
        self.assertEqual(executor.calls, [])
        settings.periodic_enabled = False
        service._components.return_value = (settings, Enumerator([movie(1)]), executor)
        self.assertEqual(service.run_background()["status"], "disabled")

    def test_changed_pin_generation_disables_real_automation(self):
        service, addon, manager, _ui, store, settings, executor = self.build(
            dry_run=False, candidates=[movie(1)]
        )
        manager.settings.pin_hash = b"a" * 32
        manager.settings.pin_salt = b"b" * 16
        addon.values["pin_hash"] = manager.settings.pin_hash.hex()
        addon.values["pin_salt"] = manager.settings.pin_salt.hex()
        service.enable_periodic(authorized=True)
        store.state["next_due"] = 0
        addon.values["pin_hash"] = (b"c" * 32).hex()
        manager.settings.pin_hash = b"c" * 32
        result = service.run_background()
        self.assertEqual(result["status"], "authorization_stale")
        self.assertEqual(addon.getSetting("retention_periodic_enabled"), "false")
        self.assertEqual(executor.calls, [])

    def test_recent_committed_key_is_not_reprocessed(self):
        item = movie(1)
        service, _addon, _manager, _ui, store, _settings, executor = self.build(
            dry_run=True, candidates=[item]
        )
        store.state.update({"next_due": 0, "recent_processed": [{"key": item.stable_key, "time": time.time()}]})
        result = service.run_background()
        self.assertEqual(result["status"], "completed")
        self.assertEqual(executor.calls, [])


class DaemonTests(unittest.TestCase):
    def test_waits_for_abort_without_busy_polling(self):
        monitor = mock.MagicMock()
        monitor.waitForAbort.side_effect = [False, True]
        monitor.abortRequested.return_value = False
        service = mock.MagicMock()
        run_service(monitor, service, startup_delay=30, check_interval=3600)
        service.run_background.assert_called_once()
        self.assertEqual(monitor.waitForAbort.call_args_list, [mock.call(30.0), mock.call(3600.0)])

    def test_startup_abort_skips_run(self):
        monitor = mock.MagicMock(); monitor.waitForAbort.return_value = True
        service = mock.MagicMock()
        run_service(monitor, service)
        service.run_background.assert_not_called()


if __name__ == "__main__":
    unittest.main()
