import unittest
from unittest import mock

from arr_manager import entrypoints
from arr_manager.registry import get_action_by_id


class Addon:
    def __init__(self): self.values = {}
    def getAddonInfo(self, key): return {"name": "Kodi Managarr", "version": "1.2.0"}.get(key, "")
    def getLocalizedString(self, _string_id): return ""
    def getSetting(self, key): return self.values.get(key, "")
    def setSetting(self, key, value): self.values[key] = value


class Settings:
    debug = False
    dry_run = False
    menu_mode = "1"
    hidden_actions = []
    action_order = []
    pin_enabled = False
    pin_invalid = False
    pin_hash = b""
    pin_salt = b""
    retention = type("Retention", (), {"background_dry_run": True})()


class UI:
    def __init__(self):
        self.jsonrpc = object()
        self.selections = []
        self.notifications = []
    def select(self, heading, options): self.selections.append(list(options)); return -1
    def notification(self, message, **kwargs): self.notifications.append((message, kwargs))
    def ok(self, *args): pass
    def text(self, *args): pass
    def open_settings(self): pass
    def numeric_input(self, *args): return ""
    def confirm(self, *args): return True


class Logger:
    debug_enabled = False
    def info(self, *args): pass
    def warning(self, *args): pass
    def exception(self, *args): pass


class Service:
    last = None
    def __init__(self, *args): Service.last = self
    def run_preview(self): return "preview"
    def run_cleanup_now(self, authorized=False): return ("run", authorized)
    def enable_periodic(self, authorized=False): return ("enable", authorized)
    def disable_periodic(self): return "disable"
    def view_report(self): return "report"


class RetentionEntrypointTests(unittest.TestCase):
    def setUp(self): Service.last = None

    def run_action(self, mode, settings=None, auth=True):
        Service.last = None
        addon = Addon(); ui = UI(); settings = settings or Settings()
        with mock.patch.object(entrypoints, "ArrManager", return_value=mock.MagicMock()), \
             mock.patch.object(entrypoints, "RetentionService", Service), \
             mock.patch.object(entrypoints, "authorize_destructive", return_value=auth) as authorize:
            result = entrypoints._run_action(mode, addon, settings, Logger(), ui)
        return result, authorize, addon, ui

    def test_registry_exposes_advanced_retention_group_and_direct_modes(self):
        parent = get_action_by_id("retention")
        self.assertTrue(parent["is_submenu"])
        self.assertFalse(parent["simple_mode"])
        for action_id in (
            "retention_preview", "retention_run", "retention_enable",
            "retention_disable", "retention_report",
        ):
            action = get_action_by_id(action_id)
            self.assertIn(action["mode"], entrypoints.DIRECT_ACTIONS)
            self.assertFalse(action["requires_selection"])

    def test_preview_and_report_never_prompt_for_pin(self):
        for mode, expected in [("retention_preview", "preview"), ("retention_report", "report")]:
            with self.subTest(mode=mode):
                result, authorize, _addon, _ui = self.run_action(mode)
                self.assertEqual(result, expected)
                authorize.assert_not_called()

    def test_manual_real_cleanup_requires_central_pin(self):
        settings = Settings(); settings.dry_run = False
        result, authorize, _addon, _ui = self.run_action("retention_run", settings, auth=True)
        authorize.assert_called_once_with(settings, mock.ANY)
        self.assertEqual(result, ("run", True))

        result, authorize, _addon, _ui = self.run_action("retention_run", settings, auth=False)
        authorize.assert_called_once()
        self.assertEqual(result, "Cancelled")
        self.assertIsNone(Service.last)

    def test_manual_dry_run_does_not_prompt(self):
        settings = Settings(); settings.dry_run = True
        result, authorize, _addon, _ui = self.run_action("retention_run", settings)
        authorize.assert_not_called()
        self.assertEqual(result, ("run", True))

    def test_real_periodic_enable_requires_pin_but_dry_run_does_not(self):
        settings = Settings()
        settings.retention = type("Retention", (), {"background_dry_run": False})()
        result, authorize, _addon, _ui = self.run_action("retention_enable", settings)
        authorize.assert_called_once()
        self.assertEqual(result, ("enable", True))

        settings.retention = type("Retention", (), {"background_dry_run": True})()
        result, authorize, _addon, _ui = self.run_action("retention_enable", settings)
        authorize.assert_not_called()
        self.assertEqual(result, ("enable", True))

    def test_disabling_periodic_cleanup_never_prompts(self):
        result, authorize, _addon, _ui = self.run_action("retention_disable")
        authorize.assert_not_called()
        self.assertEqual(result, "disable")

    def test_pin_change_invalidates_periodic_cleanup(self):
        addon = Addon(); addon.values["retention_periodic_enabled"] = "true"
        settings = Settings(); ui = UI()
        ui.numeric_input = mock.MagicMock(side_effect=["1234", "1234"])
        with mock.patch.object(entrypoints, "hash_pin", return_value=(b"a" * 32, b"b" * 16)):
            entrypoints._run_manage_pin(addon, settings, Logger(), ui)
        self.assertEqual(addon.getSetting("retention_periodic_enabled"), "false")


if __name__ == "__main__":
    unittest.main()
