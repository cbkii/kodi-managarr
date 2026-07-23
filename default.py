# SPDX-License-Identifier: GPL-3.0-or-later
import os
import sys

ADDON_DIR = os.path.dirname(os.path.abspath(__file__))
LIB_DIR = os.path.join(ADDON_DIR, "resources", "lib")
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

from arr_manager.entrypoints import run_script  # noqa: E402
from arr_manager.interactive_entrypoint import INTERACTIVE_MODES, run_mode  # noqa: E402


def _mode(args):
    for arg in args:
        for part in str(arg).split("&"):
            if part.startswith("mode="):
                return part.split("=", 1)[1]
    return ""


if __name__ == "__main__":
    selected_mode = _mode(sys.argv[1:])
    if selected_mode in INTERACTIVE_MODES:
        run_mode(selected_mode)
    else:
        run_script(sys.argv[1:])
