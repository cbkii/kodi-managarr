import json
import logging
import os
import sys
import traceback

from .models import SelectedItem
from .util import as_int, redact_url


class KodiLogger:
    def __init__(self, debug=False):
        import xbmc
        self.xbmc = xbmc
        self.debug_enabled = debug

    def _write(self, level, message, *args):
        if args:
            message = message % args
        self.xbmc.log(f"[Arr Manager] {message}", level)

    def debug(self, message, *args):
        if self.debug_enabled:
            self._write(self.xbmc.LOGDEBUG, message, *args)

    def info(self, message, *args):
        self._write(self.xbmc.LOGINFO, message, *args)

    def warning(self, message, *args):
        self._write(self.xbmc.LOGWARNING, message, *args)

    def error(self, message, *args):
        self._write(self.xbmc.LOGERROR, message, *args)

    def exception(self, message):
        self.error("%s\n%s", message, traceback.format_exc())


class KodiUI:
    def __init__(self, addon):
        import xbmc
        import xbmcgui
        self.xbmc = xbmc
        self.xbmcgui = xbmcgui
        self.addon = addon
        self.name = addon.getAddonInfo("name")

    def notification(self, message, error=False, milliseconds=5000):
        icon = self.xbmcgui.NOTIFICATION_ERROR if error else self.xbmcgui.NOTIFICATION_INFO
        self.xbmcgui.Dialog().notification(self.name, message, icon, milliseconds)

    def ok(self, heading, message):
        return self.xbmcgui.Dialog().ok(heading, message)

    def confirm(self, heading, message):
        return self.xbmcgui.Dialog().yesno(heading, message, yeslabel="Continue", nolabel="Cancel")

    def select(self, heading, options):
        return self.xbmcgui.Dialog().select(heading, options)

    def progress(self, heading, message=""):
        dialog = self.xbmcgui.DialogProgress()
        dialog.create(heading, message)
        return dialog

    def open_settings(self):
        self.addon.openSettings()

    def refresh_kodi_library(self):
        # Fallback only: workflow-specific JSON-RPC cleanup is preferred where available.
        return None

    def wait_for_abort(self, seconds):
        return self.xbmc.Monitor().waitForAbort(float(seconds))


def _tag_value(tag, method, default=""):
    try:
        fn = getattr(tag, method)
        value = fn()
        return default if value is None else value
    except Exception:
        return default



def _first_present(*values):
    for value in values:
        if value is not None and value != "":
            return value
    return ""

def selected_item_from_context():
    import xbmc
    import xbmcgui

    item = getattr(sys, "listitem", None)
    tag = None
    if item is not None:
        try:
            tag = item.getVideoInfoTag()
        except Exception:
            tag = None

    def label(name):
        try:
            return xbmc.getInfoLabel(name) or ""
        except Exception:
            return ""

    unique_ids = {}
    for key in ("tmdb", "tvdb", "imdb"):
        value = ""
        if tag is not None:
            try:
                value = tag.getUniqueID(key) or ""
            except Exception:
                pass
        value = value or label(f"ListItem.UniqueID({key})")
        if value:
            unique_ids[key] = str(value)

    media_type = (_tag_value(tag, "getMediaType") if tag else "") or label("ListItem.DBType")
    title = (_tag_value(tag, "getTitle") if tag else "") or label("ListItem.Title")
    tvshow_title = (_tag_value(tag, "getTVShowTitle") if tag else "") or label("ListItem.TVShowTitle")
    file_path = ""
    if tag is not None:
        file_path = _tag_value(tag, "getFilenameAndPath") or _tag_value(tag, "getPath")
    file_path = file_path or label("ListItem.FileNameAndPath")

    return SelectedItem(
        media_type=str(media_type).lower(),
        db_id=as_int(_first_present(_tag_value(tag, "getDbId", "") if tag else "", label("ListItem.DBID")), 0),
        title=str(title),
        year=as_int(_first_present(_tag_value(tag, "getYear", "") if tag else "", label("ListItem.Year")), 0),
        tvshow_title=str(tvshow_title),
        season=as_int(_first_present(_tag_value(tag, "getSeason", "") if tag else "", label("ListItem.Season")), -1),
        episode=as_int(_first_present(_tag_value(tag, "getEpisode", "") if tag else "", label("ListItem.Episode")), -1),
        file_path=str(file_path),
        unique_ids=unique_ids,
    )
