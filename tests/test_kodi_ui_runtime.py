import os
import sys
import types
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "resources", "lib"))

from arr_manager.kodi_ui import KodiUI


class Addon:
    def getAddonInfo(self, key):
        return {"name": "Kodi Managarr"}.get(key, "")


class Monitor:
    instances = []

    def __init__(self):
        self.waits = []
        self.__class__.instances.append(self)

    def waitForAbort(self, seconds):
        self.waits.append(seconds)
        return False


class KodiUiRuntimeTests(unittest.TestCase):
    def setUp(self):
        Monitor.instances = []

    def test_waits_reuse_one_monitor_instance(self):
        xbmc = types.ModuleType("xbmc")
        xbmc.Monitor = Monitor
        xbmc.executeJSONRPC = lambda payload: payload
        xbmcgui = types.ModuleType("xbmcgui")

        with mock.patch.dict(sys.modules, {"xbmc": xbmc, "xbmcgui": xbmcgui}):
            ui = KodiUI(Addon())
            self.assertFalse(ui.wait_for_abort(0.25))
            self.assertFalse(ui.wait_for_abort(1))

        self.assertEqual(len(Monitor.instances), 1)
        self.assertEqual(Monitor.instances[0].waits, [0.25, 1.0])


if __name__ == "__main__":
    unittest.main()
