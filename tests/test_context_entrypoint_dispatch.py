import runpy
import sys
import types
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
LIB_DIR = str(ROOT / "resources" / "lib")
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

from arr_manager import entrypoints  # noqa: E402


def manifest_actions():
    addon = ET.parse(ROOT / "addon.xml").getroot()
    extension = addon.find("extension[@point='kodi.context.item']")
    if extension is None:
        raise AssertionError("addon.xml is missing kodi.context.item")
    return {
        item.attrib.get("args", "")
        for item in extension.findall(".//item")
        if item.attrib.get("args")
    }


class Settings:
    debug = False


class Logger:
    debug_enabled = False

    def warning(self, *args):
        pass

    def exception(self, *args):
        pass


class ContextEntrypointDispatchTests(unittest.TestCase):
    def test_manifest_actions_match_supported_direct_actions(self):
        self.assertEqual(manifest_actions(), set(entrypoints.DIRECT_ACTIONS))

    def test_context_script_forwards_every_manifest_action(self):
        for action in sorted(manifest_actions()):
            with self.subTest(action=action):
                forwarded = []
                fake_package = types.ModuleType("arr_manager")
                fake_package.__path__ = []
                fake_entrypoints = types.ModuleType("arr_manager.entrypoints")
                fake_entrypoints.run_context = forwarded.append
                with mock.patch.dict(
                    sys.modules,
                    {
                        "arr_manager": fake_package,
                        "arr_manager.entrypoints": fake_entrypoints,
                    },
                ), mock.patch.object(sys, "path", list(sys.path)), mock.patch.object(
                    sys,
                    "argv",
                    [str(ROOT / "context.py"), action],
                ):
                    runpy.run_path(str(ROOT / "context.py"), run_name="__main__")
                self.assertEqual(forwarded, [action])

    def test_run_context_dispatches_every_manifest_action(self):
        addon = object()
        settings = Settings()
        logger = Logger()
        ui = object()
        for action in sorted(manifest_actions()):
            with self.subTest(action=action), mock.patch.object(
                entrypoints,
                "_bootstrap",
                return_value=(addon, logger, ui),
            ), mock.patch.object(
                entrypoints,
                "Settings",
                return_value=settings,
            ), mock.patch.object(entrypoints, "_run_action") as dispatch:
                entrypoints.run_context(action)
                dispatch.assert_called_once_with(action, addon, settings, logger, ui)


if __name__ == "__main__":
    unittest.main()
