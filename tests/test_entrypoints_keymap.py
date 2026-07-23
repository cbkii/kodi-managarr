import os
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "resources", "lib"))

from arr_manager import entrypoints
from arr_manager.errors import ConfigurationError
from arr_manager.models import SelectedItem


class Addon:
    def __init__(self): self.values = {}
    def getAddonInfo(self, key): return {"name": "Kodi Managarr", "profile": "special://profile/addon_data/context.arr.manager", "version": "1.1.1"}.get(key, "")
    def getLocalizedString(self, string_id): return ""
    def getSetting(self, key): return self.values.get(key, "")
    def setSetting(self, key, value): self.values[key] = value


class UI:
    def __init__(self, choices=(), numeric=()):
        self.choices = list(choices); self.numeric = list(numeric); self.selections = []
        self.opened = False; self.dialogs = []; self.notifications = []; self.texts = []
    def select(self, heading, options): self.selections.append((heading, list(options))); return self.choices.pop(0)
    def open_settings(self): self.opened = True
    def ok(self, heading, message): self.dialogs.append((heading, message))
    def notification(self, message, **kwargs): self.notifications.append(message)
    def text(self, heading, message): self.texts.append((heading, message))
    def numeric_input(self, heading, default=""): return self.numeric.pop(0) if self.numeric else ""
    def confirm(self, heading, message): return True


class Logger:
    debug_enabled = False
    def debug(self, *args): pass
    def info(self, *args): pass
    def warning(self, *args): pass
    def exception(self, *args): pass


class Settings:
    debug = False
    menu_mode = "1"
    hidden_actions = []
    action_order = []
    pin_enabled = False
    pin_invalid = False
    pin_hash = b""
    pin_salt = b""


class Manager:
    calls = []
    def __init__(self, settings, ui, logger): self.ui = ui
    def execute(self, action, selected): self.calls.append(action); return "done"


class EntrypointTests(unittest.TestCase):
    def setUp(self): Manager.calls = []

    def run_script(self, choices, args=(), settings=None):
        ui = UI(choices)
        with mock.patch.object(entrypoints, "_bootstrap", return_value=(Addon(), Logger(), ui)), \
             mock.patch.object(entrypoints, "Settings", return_value=settings or Settings()), \
             mock.patch.object(entrypoints, "selected_item_from_context", return_value=SelectedItem(media_type="movie", title="Film")), \
             mock.patch.object(entrypoints, "ArrManager", Manager):
            entrypoints.run_script(list(args))
        return ui

    def test_launcher_exposes_complete_native_scope_by_default(self):
        ui = self.run_script([0])
        self.assertEqual(ui.selections[0][1], [
            "Request & Search", "Status", "Search & download now", "Interactive search",
            "Monitoring", "Download queue", "Dashboard", "Find subtitles",
            "Delete & Exclude", "Delete & Replace", "Configure Request & Search defaults",
            "Configure subtitle languages", "Tools & settings",
        ])
        self.assertEqual(Manager.calls, ["request_search"])

    def test_simple_mode_is_remote_friendly(self):
        settings = Settings(); settings.menu_mode = "0"
        ui = self.run_script([0], settings=settings)
        self.assertEqual(ui.selections[0][1], [
            "Request & Search", "Status", "Search & download now", "Dashboard",
            "Find subtitles", "Delete & Exclude", "Delete & Replace", "Tools & settings",
        ])

    def test_direct_context_action_skips_launcher_even_when_hidden(self):
        settings = Settings(); settings.hidden_actions = ["search_now"]
        ui = self.run_script([], ["mode=search_now"], settings=settings)
        self.assertEqual(ui.selections, [])
        self.assertEqual(Manager.calls, ["search_now"])

    def test_invalid_configuration_still_opens_settings(self):
        ui = UI()
        with mock.patch.object(entrypoints, "_bootstrap", return_value=(Addon(), Logger(), ui)), \
             mock.patch.object(entrypoints, "Settings", side_effect=ConfigurationError("bad mapping")):
            entrypoints.run_script([])
        self.assertTrue(ui.opened)
        self.assertTrue(ui.dialogs)


class WriteDiagnosticsTests(unittest.TestCase):
    @staticmethod
    def settings():
        settings = Settings()
        settings.backend = "api"; settings.dry_run = False; settings.require_blocklist = True
        config = type("MockConfig", (), {"url": "", "api_key": "", "api_version": "", "verify_tls": True})
        settings.radarr = config(); settings.sonarr = config()
        settings.path_mapper = type("MockPathMapper", (), {"mappings": []})()
        settings.protected_paths = []
        return settings

    def run_case(self, first_error, logger):
        addon = Addon()
        write_handle = mock.mock_open().return_value
        with mock.patch("arr_manager.entrypoints.os.makedirs"), \
             mock.patch("arr_manager.entrypoints.open", side_effect=[first_error, write_handle]), \
             mock.patch.dict("sys.modules", {"xbmc": mock.MagicMock(), "xbmcvfs": mock.MagicMock()}), \
             mock.patch("arr_manager.entrypoints.json.dump") as dump:
            entrypoints._write_diagnostics(addon, self.settings(), logger)
            return dump.call_args[0][0]

    def test_missing_state_is_normal(self):
        logger = mock.MagicMock()
        payload = self.run_case(FileNotFoundError("missing"), logger)
        self.assertIsNone(payload["lastTransactionStatus"])
        logger.warning.assert_not_called()

    def test_malformed_state_is_logged_safely(self):
        logger = mock.MagicMock()
        payload = self.run_case(ValueError("secret body"), logger)
        self.assertIsNone(payload["lastTransactionStatus"])
        logger.warning.assert_called_once_with("Could not read non-secret transaction state: %s", "ValueError")

    def test_unreadable_state_is_logged_safely(self):
        logger = mock.MagicMock()
        payload = self.run_case(PermissionError("private path"), logger)
        self.assertIsNone(payload["lastTransactionStatus"])
        logger.warning.assert_called_once_with("Could not read non-secret transaction state: %s", "PermissionError")


if __name__ == "__main__":
    unittest.main()
