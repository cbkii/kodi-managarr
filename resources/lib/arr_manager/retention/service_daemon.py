# SPDX-License-Identifier: GPL-3.0-or-later
import time

def run_service(kodi_monitor, retention_service):
    # Wait initially to avoid running immediately in a tight startup loop
    if kodi_monitor.waitForAbort(30):
        return

    while not kodi_monitor.abortRequested():
        try:
            retention_service.run_background()
        except Exception as e:
            if retention_service.logger:
                retention_service.logger.error("Retention background pass failed: %s", e)

        # Sleep for a bit before checking again, wake up early if Kodi aborts
        if kodi_monitor.waitForAbort(3600): # Check every hour for due tasks
            break
