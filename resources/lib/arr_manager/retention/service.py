# SPDX-License-Identifier: GPL-3.0-or-later
import time

from ..config import Settings
from .config import RetentionSettings
from .controller import RetentionController


def run_service(addon, ui, logger):
    # Keep startup light and never use modal dialogs from the background path.
    while not ui.wait_for_abort(60):
        try:
            settings = Settings(addon)
            logger.debug_enabled = settings.debug
            retention = RetentionSettings.from_addon(addon)
            if not retention.enabled or not retention.periodic_enabled:
                continue
            controller = RetentionController(addon, settings, ui, logger)
            state = controller.state.load_state()
            next_due = float(state.get("next_due") or 0)
            if next_due <= 0:
                controller.state.save_state(
                    next_due=time.time() + retention.interval_hours * 3600,
                    last_status="scheduled",
                )
                continue
            if time.time() >= next_due:
                controller.run(scheduled=True)
        except Exception as exc:
            logger.error("Scheduled retention iteration failed: %s", type(exc).__name__)
            # A failing iteration is bounded by the outer wait; do not crash Kodi or spin.
