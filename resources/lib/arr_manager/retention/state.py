# SPDX-License-Identifier: GPL-3.0-or-later
import json
import os
import time
import uuid

from ..errors import SafetyError


class RetentionStateStore:
    SCHEMA = 1

    def __init__(self, profile):
        self.profile = profile
        os.makedirs(profile, exist_ok=True)
        self.state_path = os.path.join(profile, "retention_state.json")
        self.report_path = os.path.join(profile, "retention_last_report.json")
        self.lock_path = os.path.join(profile, "retention.lock")
        self.lock_token = ""

    @staticmethod
    def _atomic_json(path, payload):
        temporary = path + ".tmp"
        with open(temporary, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, sort_keys=True, separators=(",", ":"))
        try:
            os.chmod(temporary, 0o600)
        except OSError:
            pass
        os.replace(temporary, path)

    def load_state(self):
        if not os.path.exists(self.state_path):
            return {"schema": self.SCHEMA}
        try:
            with open(self.state_path, encoding="utf-8") as handle:
                value = json.load(handle)
        except (OSError, ValueError) as exc:
            raise SafetyError("Retention schedule state is unreadable") from exc
        if not isinstance(value, dict) or value.get("schema") != self.SCHEMA:
            raise SafetyError("Retention schedule state is malformed")
        return value

    def save_state(self, **values):
        state = self.load_state()
        state.update(values)
        state["schema"] = self.SCHEMA
        self._atomic_json(self.state_path, state)

    def save_report(self, report):
        payload = dict(report)
        payload["schema"] = self.SCHEMA
        self._atomic_json(self.report_path, payload)

    def load_report(self):
        if not os.path.exists(self.report_path):
            return {}
        try:
            with open(self.report_path, encoding="utf-8") as handle:
                value = json.load(handle)
        except (OSError, ValueError) as exc:
            raise SafetyError("Retention report is unreadable") from exc
        if not isinstance(value, dict) or value.get("schema") != self.SCHEMA:
            raise SafetyError("Retention report is malformed")
        return value

    def acquire_lock(self, stale_after=3600):
        now = time.time()
        if os.path.exists(self.lock_path):
            try:
                if now - os.path.getmtime(self.lock_path) > stale_after:
                    os.remove(self.lock_path)
                else:
                    return False
            except OSError:
                return False
        token = uuid.uuid4().hex
        try:
            descriptor = os.open(self.lock_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            return False
        except OSError:
            return False
        try:
            os.write(descriptor, token.encode("ascii"))
        finally:
            os.close(descriptor)
        self.lock_token = token
        return True

    def release_lock(self):
        if not self.lock_token:
            return
        try:
            with open(self.lock_path, encoding="ascii") as handle:
                owner = handle.read().strip()
            if owner == self.lock_token:
                os.remove(self.lock_path)
        except OSError:
            pass
        self.lock_token = ""
