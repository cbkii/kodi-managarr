import os
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "resources", "lib"))

from arr_manager import entrypoints
from arr_manager.models import SelectedItem


class FakeAddon:
    STRINGS = {
        32001: "Delete & Exclude",
        32002: "Delete & Replace",
        32500: "Tools & settings",
        32501: "Open settings",
        32502: "Test Radarr",
        32503: "Test Sonarr",
        32504: "Test file backend",
        32505: "Write diagnostics",
    }

    def getAddonInfo(self, key):
        return {
            "name": "Kodi Managarr",
            "profile": "special://profile/addon_data/context.arr.manager",
            "version": "0.1.1",
        }.get(key, "")

    def getLocalizedString(self, string_id):
        return self.STRINGS.get(string_id, "")


class FakeUI:
    def __init__(self, choices):
        self.choices = list(choices)
        self.selections = []
        self.notifications = []
        self.opened_settings = False
        self.dialogs = []

    def select(self, heading, options):
        self.selections.append((heading, list(options)))
        return self.choices.pop(0)

    def notification(self, message, error=False, milliseconds=5000):
        self.notifications.append((message, error, milliseconds))

    def open_settings(self):
        self.opened_settings = True

    def ok(self, heading, message):
        self.dialogs.append((heading, message))


class FakeLogger:
    def info(self, *args):
        pass

    def warning(self, *args):
        pass

    def exception(self, *args):
        pass


class FakeManager:
    calls = []

    def __init__(self, settings, ui, logger):
        self.settings = settings
        self.ui = ui
        self.logger = logger

    def execute(self, action, selected):
        self.calls.append((action, selected))
        return "completed"


class KeymapEntrypointTests(unittest.TestCase):
    def setUp(self):
        FakeManager.calls = []
        self.addon = FakeAddon()
        self.settings = object()
        self.logger = FakeLogger()
        self.selected = SelectedItem(media_type="movie", db_id=42, title="Example", year=2024)

    def run_script(self, args, choices):
        ui = FakeUI(choices)
        with mock.patch.object(
            entrypoints,
            "_runtime",
            return_value=(self.addon, self.settings, self.logger, ui),
        ), mock.patch.object(
            entrypoints,
            "selected_item_from_context",
            return_value=self.selected,
        ), mock.patch.object(entrypoints, "ArrManager", FakeManager):
            entrypoints.run_script(args)
        return ui

    def test_keymap_launcher_offers_actions_before_tools(self):
        ui = self.run_script([], [0])

        self.assertEqual(
            ui.selections,
            [
                (
                    "Kodi Managarr",
                    ["Delete & Exclude", "Delete & Replace", "Tools & settings"],
                )
            ],
        )
        self.assertEqual(FakeManager.calls, [("delete_exclude", self.selected)])
        self.assertEqual(ui.notifications, [("completed", False, 5000)])

    def test_keymap_launcher_runs_replace_choice(self):
        self.run_script([], [1])

        self.assertEqual(FakeManager.calls, [("delete_replace", self.selected)])

    def test_keymap_launcher_keeps_tools_available(self):
        ui = self.run_script([], [2, 0])

        self.assertTrue(ui.opened_settings)
        self.assertEqual(FakeManager.calls, [])
        self.assertEqual(
            ui.selections[1],
            (
                "Kodi Managarr",
                [
                    "Open settings",
                    "Test Radarr",
                    "Test Sonarr",
                    "Test file backend",
                    "Write diagnostics",
                ],
            ),
        )

    def test_direct_keymap_mode_runs_without_chooser(self):
        ui = self.run_script(["mode=delete_replace"], [])

        self.assertEqual(ui.selections, [])
        self.assertEqual(FakeManager.calls, [("delete_replace", self.selected)])

    def test_cancelled_launcher_makes_no_changes(self):
        ui = self.run_script([], [-1])

        self.assertEqual(FakeManager.calls, [])
        self.assertEqual(ui.notifications, [])

    def test_launcher_without_active_library_item_shows_clean_error(self):
        self.selected = SelectedItem(media_type="", title="")
        ui = self.run_script(["mode=delete_replace"], [])

        self.assertEqual(FakeManager.calls, [])
        self.assertEqual(ui.notifications, [])
        self.assertEqual(
            ui.dialogs,
            [
                (
                    "Kodi Managarr",
                    "No active Kodi library movie, TV show, or episode is selected.",
                )
            ],
        )


if __name__ == "__main__":
    unittest.main()
