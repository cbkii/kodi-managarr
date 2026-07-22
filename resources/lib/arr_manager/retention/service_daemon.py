# SPDX-License-Identifier: GPL-3.0-or-later


def run_service(kodi_monitor, retention_service, startup_delay=30, check_interval=3600):
    if kodi_monitor.waitForAbort(float(startup_delay)):
        return
    while not kodi_monitor.abortRequested():
        retention_service.run_background(abort_checker=kodi_monitor.abortRequested)
        if kodi_monitor.waitForAbort(float(check_interval)):
            return
