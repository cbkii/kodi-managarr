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
    def getAddonInfo(self, key): return {"name": "Kodi Managarr", "profile": "special://profile/addon_data/context.arr.manager", "version": "0.2.0"}.get(key, "")
    def getLocalizedString(self, string_id): return ""
    def getSetting(self, key): return ""


class UI:
    def __init__(self, choices=()): self.choices = list(choices); self.selections = []; self.opened = False; self.dialogs = []; self.notifications = []; self.texts = []
    def select(self, heading, options): self.selections.append((heading, list(options))); return self.choices.pop(0)
    def open_settings(self): self.opened = True
    def ok(self, heading, message): self.dialogs.append((heading, message))
    def notification(self, message, **kwargs): self.notifications.append(message)
    def text(self, heading, message): self.texts.append((heading, message))


class Logger:
    debug_enabled = False
    def debug(self, *args): pass
    def info(self, *args): pass
    def warning(self, *args): pass
    def exception(self, *args): pass


class Settings:
    debug = False


class Manager:
    calls = []
    def __init__(self, settings, ui, logger): self.ui = ui
    def execute(self, action, selected): self.calls.append(action); return "done"


class EntrypointTests(unittest.TestCase):
    def setUp(self): Manager.calls = []

    def run_script(self, choices, args=()):
        ui = UI(choices)
        with mock.patch.object(entrypoints, "_bootstrap", return_value=(Addon(), Logger(), ui)), \
             mock.patch.object(entrypoints, "Settings", return_value=Settings()), \
             mock.patch.object(entrypoints, "selected_item_from_context", return_value=SelectedItem(media_type="movie", title="Film")), \
             mock.patch.object(entrypoints, "ArrManager", Manager):
            entrypoints.run_script(list(args))
        return ui

    def test_launcher_exposes_complete_native_scope(self):
        pass

if __name__ == "__main__":
    unittest.main()
