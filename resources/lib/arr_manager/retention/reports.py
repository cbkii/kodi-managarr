# SPDX-License-Identifier: GPL-3.0-or-later
import os
import json
import time

class RetentionStateStore:
    def __init__(self, addon):
        import xbmcvfs
        self.profile = xbmcvfs.translatePath(addon.getAddonInfo("profile"))
        os.makedirs(self.profile, exist_ok=True)
        self.state_file = os.path.join(self.profile, "retention_state.json")
        self.report_file = os.path.join(self.profile, "retention_last_report.json")
        self.lock_file = os.path.join(self.profile, "retention.lock")

    def acquire_lock(self, timeout_minutes=30):
        # Stale lock recovery
        if os.path.exists(self.lock_file):
            try:
                mtime = os.path.getmtime(self.lock_file)
                if time.time() - mtime > timeout_minutes * 60:
                    os.remove(self.lock_file)
                else:
                    return False
            except Exception:
                pass

        try:
            with open(self.lock_file, "w") as f:
                f.write(str(time.time()))
            return True
        except Exception:
            return False

    def release_lock(self):
        try:
            if os.path.exists(self.lock_file):
                os.remove(self.lock_file)
        except Exception:
            pass

    def save_state(self, auth_generation, next_due):
        state = {
            "auth_generation": auth_generation,
            "next_due": next_due
        }
        try:
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(state, f)
        except Exception:
            pass

    def load_state(self):
        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def save_report(self, report_data):
        try:
            with open(self.report_file, "w", encoding="utf-8") as f:
                json.dump(report_data, f, indent=2)
        except Exception:
            pass

    def load_report(self):
         try:
            with open(self.report_file, "r", encoding="utf-8") as f:
                return json.load(f)
         except Exception:
            return {}
