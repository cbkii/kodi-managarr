# SPDX-License-Identifier: GPL-3.0-or-later
"""Kodi subtitle-provider entrypoint with a complete bootstrap error boundary."""

import importlib
import os
import sys
from urllib.parse import parse_qs, urlsplit

ADDON_DIR = os.path.dirname(os.path.abspath(__file__))
LIB_DIR = os.path.join(ADDON_DIR, "resources", "lib")
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

# Preserve explicitly preloaded Kodi modules used by host-side tests without
# importing runtime modules before the protected bootstrap boundary.
for _module_name in ("xbmcaddon", "xbmcgui", "xbmcplugin", "xbmcvfs"):
    if _module_name in sys.modules:
        globals()[_module_name] = sys.modules[_module_name]


def _bootstrap_log(message, level=None):
    try:
        xbmc = importlib.import_module("xbmc")
        xbmc.log(f"[Managarr subtitles] {message}", xbmc.LOGINFO if level is None else level)
    except Exception:
        pass


def _query_params(argv):
    raw = ""
    if len(argv) > 2 and argv[2]:
        raw = str(argv[2]).lstrip("?")
    elif argv:
        raw = urlsplit(str(argv[0])).query
    return {key: values[-1] for key, values in parse_qs(raw, keep_blank_values=True).items() if values}


def _component(global_name, module_name, attribute=None):
    injected = globals().get(global_name)
    if injected is not None:
        return injected
    module = importlib.import_module(module_name)
    if module_name == "arr_manager.subtitle_service":
        hardening = importlib.import_module("arr_manager.subtitle_hardening")
        hardening.install(module)
    return getattr(module, attribute) if attribute else module


def _safe_error_type(exc):
    name = type(exc).__name__
    return name if name and name.isidentifier() else "SubtitleError"


def main(argv):
    handle = None
    succeeded = False
    plugin = None
    logger = None
    addon = None
    ui = None
    imessage_func = None
    _bootstrap_log("provider entry")
    try:
        xbmcaddon_module = _component("xbmcaddon", "xbmcaddon")
        xbmcgui_module = _component("xbmcgui", "xbmcgui")
        plugin = _component("xbmcplugin", "xbmcplugin")
        xbmcvfs_module = _component("xbmcvfs", "xbmcvfs")
        SettingsClass = _component("Settings", "arr_manager.config", "Settings")
        imessage_func = _component("imessage", "arr_manager.interactive_messages", "imessage")
        KodiLoggerClass = _component("KodiLogger", "arr_manager.kodi", "KodiLogger")
        KodiUIClass = _component("KodiUI", "arr_manager.kodi", "KodiUI")
        SubtitleServiceClass = _component("SubtitleService", "arr_manager.subtitle_service", "SubtitleService")

        if len(argv) < 2:
            raise ValueError("Kodi subtitle provider did not supply a directory handle")
        handle = int(argv[1])
        if handle < 0:
            raise ValueError("Kodi subtitle provider supplied an invalid directory handle")
        params = _query_params(argv)
        action = str(params.get("action") or "search").strip().lower()
        _bootstrap_log(f"dispatch action={action}")

        addon = xbmcaddon_module.Addon(id="context.arr.manager")
        logger = KodiLoggerClass(False)
        ui = KodiUIClass(addon)
        settings = SettingsClass(addon)
        logger.debug_enabled = settings.debug
        service = SubtitleServiceClass(addon, settings, ui, logger, ui.jsonrpc, xbmcvfs_module)

        if action in {"search", "manualsearch"}:
            _bootstrap_log("search entered")
            rows = service.search(argv[0])
            if not rows:
                ui.notification(imessage_func(addon, "subtitle_no_results"))
            for row in rows:
                item = xbmcgui_module.ListItem(label=row["label"], label2=row["label2"])
                plugin.addDirectoryItem(handle, row["url"], item, isFolder=False)
        elif action == "download":
            _bootstrap_log("download entered")
            path = service.download(params.get("token"))
            item = xbmcgui_module.ListItem(label=imessage_func(addon, "subtitle_downloaded"))
            item.setPath(path)
            plugin.addDirectoryItem(handle, path, item, isFolder=False)
        else:
            raise ValueError(imessage_func(addon, "subtitle_action_unknown"))
        succeeded = True
    except Exception as exc:
        error_type = _safe_error_type(exc)
        _bootstrap_log(f"provider failure type={error_type}")
        if logger is not None:
            logger.error("Subtitle action failed: %s", error_type)
        if ui is not None and addon is not None and imessage_func is not None:
            try:
                ui.notification(imessage_func(addon, "subtitle_search_failed", error_type=error_type), error=True)
            except Exception:
                pass
    finally:
        if handle is not None and plugin is not None:
            try:
                plugin.endOfDirectory(handle, succeeded=succeeded, cacheToDisc=False)
            except Exception:
                _bootstrap_log("directory completion failed")
    return succeeded


if __name__ == "__main__":
    main(sys.argv)
