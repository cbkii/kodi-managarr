# SPDX-License-Identifier: GPL-3.0-or-later
import sys, os, xbmc, xbmcaddon
addon = xbmcaddon.Addon(id="context.arr.manager")
sys.path.insert(0, os.path.join(xbmc.translatePath(addon.getAddonInfo("path")), "resources", "lib"))
from arr_manager.kodi import KodiLogger, KodiUI
from arr_manager.config import Settings
from arr_manager.actions import ArrManager
from arr_manager.retention.service import RetentionService
from arr_manager.retention.service_daemon import run_service
if __name__ == "__main__":
    ui = KodiUI(addon)
    settings = Settings(addon)
    run_service(ui.monitor, RetentionService(ArrManager(settings, ui, KodiLogger(addon)), ui.jsonrpc, ui, KodiLogger(addon), settings.retention_authoriser))
