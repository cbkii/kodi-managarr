# SPDX-License-Identifier: GPL-3.0-or-later
import os
import sys
from urllib.parse import parse_qs

ADDON_DIR = os.path.dirname(os.path.abspath(__file__))
LIB_DIR = os.path.join(ADDON_DIR, "resources", "lib")
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

import xbmcaddon  # noqa: E402
import xbmcgui  # noqa: E402
import xbmcplugin  # noqa: E402
import xbmcvfs  # noqa: E402

from arr_manager.config import Settings  # noqa: E402
from arr_manager.interactive_messages import imessage  # noqa: E402
from arr_manager.kodi import KodiLogger, KodiUI  # noqa: E402
from arr_manager.subtitle_service import SubtitleService  # noqa: E402


def main(argv):
    handle = int(argv[1])
    raw = argv[2][1:] if len(argv) > 2 and argv[2].startswith("?") else ""
    params = {key: values[-1] for key, values in parse_qs(raw).items() if values}
    action = params.get("action", "search")
    addon = xbmcaddon.Addon(id="context.arr.manager")
    logger = KodiLogger(False)
    ui = KodiUI(addon)
    try:
        settings = Settings(addon)
        logger.debug_enabled = settings.debug
        service = SubtitleService(addon, settings, ui, logger, ui.jsonrpc, xbmcvfs)
        if action in {"search", "manualsearch"}:
            rows = service.search(argv[0])
            if not rows:
                ui.notification(imessage(addon, "subtitle_no_results"))
            for row in rows:
                item = xbmcgui.ListItem(label=row["label"], label2=row["label2"])
                xbmcplugin.addDirectoryItem(handle, row["url"], item, isFolder=False)
        elif action == "download":
            path = service.download(params.get("token"))
            item = xbmcgui.ListItem(label=imessage(addon, "subtitle_downloaded"))
            item.setPath(path)
            xbmcplugin.addDirectoryItem(handle, path, item, isFolder=False)
        else:
            raise ValueError(imessage(addon, "subtitle_action_unknown"))
    except Exception as exc:
        logger.error("Subtitle action failed: %s", type(exc).__name__)
        ui.notification(imessage(addon, "subtitle_search_failed", error_type=type(exc).__name__), error=True)
    finally:
        xbmcplugin.endOfDirectory(handle)


if __name__ == "__main__":
    main(sys.argv)
