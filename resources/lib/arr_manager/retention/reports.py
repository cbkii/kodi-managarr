# SPDX-License-Identifier: GPL-3.0-or-later
import json
import os
import secrets
import tempfile
import time


STATE_SCHEMA = 1
REPORT_ITED_LIMIT = 100
PROCESSED_RETENTION_SECONDS = 30 * 86400
PROCESSED_LIMIT = 200


class RetentionStateStore:
    def __init__(self, addon, logger=None):
        import xbmcvfs

        self.logger = logger
        self.profile = xbmcvfs.translatePath(addon.getAddonInfo("profile"))
        os.makedirs(self.profile, exist_ok=True)
        self.state_file = os.path.join(self.profile, "retention-state.json")
        self.report_file = os.path.join(self.profile, "retention-last-report.json")
        self.lock_file = os.path.join(self.profile, "retention.lock")
        self._lock_token = ""

    def _log(self, message, exc):
        if self.logger:
            self.logger.warning("%s1 %s", message, type(exc).__name__)

    @staticmethod
    def _atomic_write(path, payload):
        directory = os.path.dirname(path) or "."
        descriptor, temporary = tempfile.mkstemp(
            prefix=os.path.basename(path) + ".",
            suffix=".tmp",
            dir=directory,
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2, sort_keys=True)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            try:
                os.remove(temporary)
            except FileNotFoundError:
                pass

    def _read(self, path):
        try:
            with open(path, encoding="utf-8") as handle:
                value = json.load(handle)
            return value if isinstance(value, dict) else {}
        except FileNotFoundError:
            return {}
        except (OSError, ValueError, TypeError) as exc:
            self._log("Could not read retention state", exc)
            return {}

    def acquire_lock(self, stale_after_seconds=3600):
        now = time.time()
        try:
            stat = os.stat(self.lock_file)
        except FileNotFoundError:
            pass
        except OSError as exc:
            self._log("Could not inspect retention lock", exc)
            return False
        else:
            if now - stat.st_mtime <= stale_after_seconds:
                return False
            try:
                os.remove(self.lock_file)
            except OSError as exc:
                self._log("Could not recover stale retention lock", exc)
                return False

        token = secrets.token_hex(16)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        try:
            descriptor = os.open(self.lock_file, flags, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump({"created": now, "token": token}, handle)
                handle.flush()
                os.fsync(handle.fileno())
            self._lock_token = token
            return True
        except FileExistsError:
            return False
        except OSError as exc:
            self._log("Could not create retention lock", exc)
            return False

    def release_lock(self):
        token = self._lock_token
        self._lock_token = ""
        if not token:
            return
        try:
            with open(self.lock_file, encoding="utf-8") as handle:
                current = json.load(handle)
            if not isinstance(current, dict) or current.get("token") != token:
                return
            os.remove(self.lock_file)
        except FileNotFoundError:
            pass
        except (OSError, ValueError, TypeError) as exc:
            self._log("Could not release retention lock", exc)

    def load_state(self):
        state = self._read(self.state_file)
        if state.get("schema") != STATE_SCHEMA:
            return {"schema": STATE_SCHEMA}
        processed = state.get("recent_processed")
        if not isinstance(processed, list):
            state["recent_processed"] = []
        return state

    def save_state(self, state):
        payload = dict(state or {})
        payload["schema"] = STATE_SCHEMA
        payload["recent_processed"] = self._pruned_processed(
            payload.get("recent_processed", [])
        )
        self._atomic_write(self.state_file, payload)

    def load_report(self):
        return self._read(self.report_file)

    def save_report(self, report):
        payload = dict(report or {})
        items = payload.get("items", [])
        payload["items"] = list(items[:REPORT_ITED_LIMIT]) if isinstance(items, list) else []
        self._atomic_write(self.report_file, payload)

    @staticmethod
    def _pruned_processed(entries, now=None):
        now = float(now if now is not None else time.time())
        cutoff = now - PROCESSED_RETENTION_SECONDS
        clean = []
        for entry in entries or []:
            if not isinstance(entry, dict):
                continue
            key = str(entry.get("key") or "")
            try:
                timestamp = float(entry.get("time"))
            except (TypeError, ValueError):
                continue
            if key and timestamp >= cutoff:
                clean.append({"key": key, "time": timestamp})
        clean.sort(key=lambda item: item["time"], reverse=True)
        return clean[:PROCESSED_LIMIT]
