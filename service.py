# SPDX-License-Identifier: GPL-3.0-or-later
import os
import sys

ADDON_DIR = os.path.dirname(os.path.abspath(__file__))
LIB_DIR = os.path.join(ADDON_DIR, "resources", "lib")
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

import xbmcaddon  # noqa: E402

from arr_manager.kodi import KodiLogger, KodiUI  # noqa: E402
from arr_manager.retention.service import run_service  # noqa: E402


if __name__ == "__main__":
    addon = xbmcaddon.Addon(id="context.arr.manager")
    run_service(addon, KodiUI(addon), KodiLogger(False))
