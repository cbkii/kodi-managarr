# SPDX-License-Identifier: GPL-3.0-or-later
import os
import sys

ADDON_DIR = os.path.dirname(os.path.abspath(__file__))
LIB_DIR = os.path.join(ADDON_DIR, "resources", "lib")
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

from arr_manager.entrypoints import run_context  # noqa: E402

if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    run_context(action)
