# SPDX-License-Identifier: GPL-3.0-or-later
import os
import sys

ADDON_DIR = os.path.dirname(os.path.abspath(__file__))
LIB_DIR = os.path.join(ADDON_DIR, "resources", "lib")
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

import arr_manager.entrypoints as _entrypoints  # noqa: E402
from arr_manager.diagnostics_hardening import install as _install_diagnostics_hardening  # noqa: E402

_install_diagnostics_hardening(_entrypoints)
run_script = _entrypoints.run_script


if __name__ == "__main__":
    run_script(sys.argv[1:])
