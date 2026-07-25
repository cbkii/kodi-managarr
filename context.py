# SPDX-License-Identifier: GPL-3.0-or-later
import os
import sys

ADDON_DIR = os.path.dirname(os.path.abspath(__file__))
LIB_DIR = os.path.join(ADDON_DIR, "resources", "lib")
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

import arr_manager.entrypoints as _entrypoints  # noqa: E402

if hasattr(_entrypoints, "_write_diagnostics"):
    from arr_manager.diagnostics_hardening import install as _install_diagnostics_hardening  # noqa: E402
    _install_diagnostics_hardening(_entrypoints)
if hasattr(_entrypoints, "_run_action") and hasattr(_entrypoints, "Settings"):
    from arr_manager.menu_entrypoints import install as _install_menu_layout  # noqa: E402
    _install_menu_layout(_entrypoints)
run_context = _entrypoints.run_context

if __name__ == "__main__":
    run_context(sys.argv[1] if len(sys.argv) > 1 else "")
