# SPDX-License-Identifier: GPL-3.0-or-later
import os
import sys

ADDON_DIR = os.path.dirname(os.path.abspath(__file__))
LIB_DIR = os.path.join(ADDON_DIR, "resources", "lib")
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

from arr_manager.kodi import KodiLogger, KodiUI  # noqa: E402
from arr_manager.retention.service import RetentionService  # noqa: E402
from arr_manager.retention.service_daemon import run_service  # noqa: E402


def main():
    import xbmc
    import xbmcaddon

    addon = xbmcaddon.Addon(id="context.arr.manager")
    logger = KodiLogger(False)
    try:
        ui = KodiUI(addon)
        retention = RetentionService(
            None,
            ui.jsonrpc,
            ui,
            logger,
            addon=addon,
        )
        run_service(xbmc.Monitor(), retention)
    except Exception as exc:
        logger.error("Retention service startup failed: %s", type(exc).__name__)


if __name__ == "__main__":
    main()
