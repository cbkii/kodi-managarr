import os
import sys
import types
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "resources", "lib"))

from arr_manager.kodi import selected_item_from_context


class Tag:
    def getMediaType(self): return "episode"
    def getTitle(self): return "Special"
    def getTVShowTitle(self): return "Show"
    def getFilenameAndPath(self): return "smb://pi/Shows/Special.mkv"
    def getDbId(self): return 0
    def getYear(self): return 0
    def getSeason(self): return 0
    def getEpisode(self): return 0
    def getUniqueID(self, key): return "123" if key == "tvdb" else ""

class Item:
    def getVideoInfoTag(self): return Tag()

class KodiSelectedItemTests(unittest.TestCase):
    def test_preserves_season_zero_and_episode_zero(self):
        old_item = getattr(sys, "listitem", None)
        old_xbmc = sys.modules.get("xbmc")
        old_xbmcgui = sys.modules.get("xbmcgui")
        sys.listitem = Item()
        sys.modules["xbmc"] = types.SimpleNamespace(getInfoLabel=lambda name: "")
        sys.modules["xbmcgui"] = types.SimpleNamespace()
        try:
            selected = selected_item_from_context()
        finally:
            if old_item is None:
                delattr(sys, "listitem")
            else:
                sys.listitem = old_item
            if old_xbmc is None:
                sys.modules.pop("xbmc", None)
            else:
                sys.modules["xbmc"] = old_xbmc
            if old_xbmcgui is None:
                sys.modules.pop("xbmcgui", None)
            else:
                sys.modules["xbmcgui"] = old_xbmcgui
        self.assertEqual(selected.season, 0)
        self.assertEqual(selected.episode, 0)

if __name__ == "__main__":
    unittest.main()
