# SPDX-License-Identifier: GPL-3.0-or-later
import os
import sys

ROOT = os.path.dirname(__file__)
LIB = os.path.join(ROOT, "resources", "lib")
if LIB not in sys.path:
    sys.path.insert(0, LIB)


def main():
    import xbmcaddon

    from arr_manager.actions import ArrManager
    from arr_manager.config import Settings
    from arr_manager.kodi import KodiLogger, KodiUI
    from arr_manager.retention import RetentionService

    addon = xbmcaddon.Addon()
    ui = KodiUI(addon)
    logger = KodiLogger(False)
    while not ui.monitor.abortRequested():
        try:
            settings = Settings(addon)
            logger.debug_enabled = settings.debug
            manager = ArrManager(settings, ui, logger)
            RetentionService(manager, ui, logger).run_background()
        except Exception:
            logger.exception("Periodic retention service pass failed")
        if ui.monitor.waitForAbort(60):
            break


if __name__ == "__main__":
    main()
