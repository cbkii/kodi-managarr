import os
import sys
import types
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "resources", "lib"))
from arr_manager.kodi import selected_item_from_context


class Tag:
    def __init__(self, db_id=0, year=0, season=0, episode=0):
        self.db_id, self.year, self.season, self.episode = db_id, year, season, episode
    def getMediaType(self): return "episode"
    def getTitle(self): return "Special"
    def getTVShowTitle(self): return "Show"
    def getFilenameAndPath(self): return "smb://pi/Shows/Special.mkv"
    def getDbId(self): return self.db_id
    def getYear(self): return self.year
    def getSeason(self): return self.season
    def getEpisode(self): return self.episode
    def getUniqueID(self, key): return "123" if key == "tvdb" else ""


class Item:
    def __init__(self, tag): self.tag = tag
    def getVideoInfoTag(self): return self.tag


class KodiSelectedItemTests(unittest.TestCase):
    def selected_with(self, tag=None, labels=None, item=None):
        labels = labels or {}
        old_item = getattr(sys, "listitem", None); old_xbmc = sys.modules.get("xbmc"); old_xbmcgui = sys.modules.get("xbmcgui")
        sys.listitem = item if item is not None else Item(tag)
        sys.modules["xbmc"] = types.SimpleNamespace(getInfoLabel=lambda name: labels.get(name, ""))
        sys.modules["xbmcgui"] = types.SimpleNamespace()
        try: return selected_item_from_context()
        finally:
            if old_item is None: delattr(sys, "listitem")
            else: sys.listitem = old_item
            if old_xbmc is None: sys.modules.pop("xbmc", None)
            else: sys.modules["xbmc"] = old_xbmc
            if old_xbmcgui is None: sys.modules.pop("xbmcgui", None)
            else: sys.modules["xbmcgui"] = old_xbmcgui

    def test_preserves_season_zero_and_episode_zero(self):
        selected = self.selected_with(Tag(season=0, episode=0))
        self.assertEqual((selected.season, selected.episode), (0, 0))

    def test_unset_values_fall_back_to_labels(self):
        selected = self.selected_with(Tag(db_id=0, year="0", season=-1, episode="-1"), {
            "ListItem.DBID": "42", "ListItem.Year": "2024", "ListItem.Season": "0", "ListItem.Episode": "7",
        })
        self.assertEqual((selected.db_id, selected.year, selected.season, selected.episode), (42, 2024, 0, 7))

    def test_listitem_getpath_fallback_used_before_labels(self):
        class EmptyPathTag(Tag):
            def getFilenameAndPath(self): return ""
            def getPath(self): return ""
        class PathItem:
            def getVideoInfoTag(self): return EmptyPathTag(db_id=1)
            def getPath(self): return "smb://pi/Movies/Path Film/file.mkv"
        selected = self.selected_with(item=PathItem(), labels={"ListItem.FileNameAndPath": "smb://pi/Other/file.mkv"})
        self.assertEqual(selected.file_path, "smb://pi/Movies/Path Film/file.mkv")


if __name__ == "__main__": unittest.main()
