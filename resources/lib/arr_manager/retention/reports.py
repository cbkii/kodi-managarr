# SPDX-License-Identifier: GPL-3.0-or-later
import json
import os
import time


class RetentionStateStore:
    def __init__(self, addon):
        import xbmcvfs

        self.profile = xbmcvfs.translatePath(addon.getAddonInfo("profile"))
        os.makedirs(self.profile, exist_ok=True)
        self.state_file = os.path.join(self.profile, "retention-state.json")
        self.report_file = os.path.join(self.profile, "retention-last-report.json")
        self.lock_file = os.path.join(self.profile, "retention.lock")

    @staticmethod
    def _read(path):
        try:
            with open(path, "r", encoding="utf-8") as handle:
                value = json.load(handle)
            return value if isinstance(value, dict) else {}
        except (OSError, ValueError, TypeError):
            return {}

    @staticmethod
    def _write(path, value):
        temporary = path + ".tmp"
        with open(temporary, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=True)
        os.replace(temporary, path)

    def load_state(self):
        return self._read(self.state_file)

    def save_state(self, auth_generation, next_due):
        self._write(self.state_file, {
            "auth_generation": str(auth_generation or ""),
            "next_due": float(next_due or 0),
        })

    def load_report(self):
        return self._read(self.report_file)

    def save_report(self, report):
        payload = dict(report or {})
        results = payload.get("results")
        if isinstance(results, list):
            payload["results"] = results[:100]
        self._write(self.report_file, payload)

    def acquire_lock(self, stale_after=1800):
        now = time.time()
        try:
            descriptor = os.open(self.lock_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            try:
                age = now - os.path.getmtime(self.lock_file)
            except OSError:
                return False
            if age <= stale_after:
                return False
            try:
                os.remove(self.lock_file)
            except OSError:
                return False
            return self.acquire_lock(stale_after=stale_after)
        except OSError:
            return False
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(str(now))
        return True

    def release_lock(self):
        try:
            os.remove(self.lock_file)
        except FileNotFoundError:
            pass
        except OSError:
            pass
