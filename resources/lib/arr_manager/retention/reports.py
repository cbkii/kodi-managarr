# SPDX-License-Identifier: GPL-3.0-or-later
import json
import math
import os
import secrets
import tempfile
import time


class RetentionStateStore:
    def __init__(self, addon):
        import xbmcvfs

        self.profile = xbmcvfs.translatePath(addon.getAddonInfo("profile"))
        os.makedirs(self.profile, exist_ok=True)
        self.state_file = os.path.join(self.profile, "retention-state.json")
        self.report_file = os.path.join(self.profile, "retention-last-report.json")
        self.lock_file = os.path.join(self.profile, "retention.lock")
        self.lock_token = None

    @staticmethod
    def _read(path):
        try:
            with open(path, "r", encoding="utf-8") as handle:
                return json.load(handle)
        except (OSError, ValueError, TypeError):
            return None

    @staticmethod
    def _write(path, value):
        directory = os.path.dirname(path) or "."
        prefix = os.path.basename(path) + "."
        descriptor, temporary = tempfile.mkstemp(prefix=prefix, suffix=".tmp", dir=directory)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(value, handle, indent=2, sort_keys=True)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            try:
                os.remove(temporary)
            except FileNotFoundError:
                pass

    def load_state(self):
        value = self._read(self.state_file)
        if not isinstance(value, dict):
            return None
        auth_generation = value.get("auth_generation")
        next_due = value.get("next_due")
        if not isinstance(auth_generation, str):
            return None
        if isinstance(next_due, bool) or not isinstance(next_due, (int, float)):
            return None
        next_due = float(next_due)
        if not math.isfinite(next_due) or next_due < 0:
            return None
        return {"auth_generation": auth_generation, "next_due": next_due}

    def save_state(self, auth_generation, next_due):
        next_due = float(next_due)
        if not math.isfinite(next_due) or next_due < 0:
            raise ValueError("Retention next_due must be a finite non-negative timestamp")
        self._write(self.state_file, {
            "auth_generation": str(auth_generation or ""),
            "next_due": next_due,
        })

    @staticmethod
    def _normalise_report(value):
        if not isinstance(value, dict):
            return None
        run_type = value.get("run_type")
        dry_run = value.get("dry_run")
        timestamp = value.get("timestamp")
        if not isinstance(run_type, str) or run_type not in {"manual", "periodic"}:
            return None
        if not isinstance(dry_run, bool):
            return None
        if isinstance(timestamp, bool) or not isinstance(timestamp, (int, float)):
            return None
        timestamp = float(timestamp)
        if not math.isfinite(timestamp) or timestamp < 0:
            return None
        payload = {"run_type": run_type, "dry_run": dry_run, "timestamp": timestamp}
        for key in ("deleted", "planned", "failed", "skipped"):
            count = value.get(key)
            if isinstance(count, bool) or not isinstance(count, int) or count < 0:
                return None
            payload[key] = count
        results = value.get("results")
        if not isinstance(results, list):
            return None
        normalised_results = []
        for item in results[:100]:
            if not isinstance(item, dict):
                return None
            normalised = {}
            for key in ("name", "action", "reason", "error"):
                text = item.get(key, "")
                if not isinstance(text, str):
                    return None
                normalised[key] = text[:2000]
            normalised_results.append(normalised)
        payload["results"] = normalised_results
        return payload

    def load_report(self):
        return self._normalise_report(self._read(self.report_file)) or {}

    def save_report(self, report):
        payload = self._normalise_report(report)
        if payload is None:
            raise ValueError("Retention report schema is invalid")
        self._write(self.report_file, payload)

    def _lock_snapshot(self):
        try:
            stat_result = os.stat(self.lock_file)
            with open(self.lock_file, "r", encoding="utf-8") as handle:
                token = handle.read(256).strip()
            return token, stat_result.st_mtime_ns, stat_result.st_mtime
        except (OSError, UnicodeError):
            return None

    def acquire_lock(self, stale_after=1800):
        if self.lock_token:
            return False
        token = secrets.token_hex(16)
        for _attempt in range(2):
            try:
                descriptor = os.open(self.lock_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            except FileExistsError:
                snapshot = self._lock_snapshot()
                if snapshot is None or time.time() - snapshot[2] <= stale_after:
                    return False
                confirmation = self._lock_snapshot()
                if confirmation is None or confirmation[:2] != snapshot[:2]:
                    return False
                try:
                    os.remove(self.lock_file)
                except OSError:
                    return False
                continue
            except OSError:
                return False
            try:
                with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                    handle.write(token)
                    handle.flush()
                    os.fsync(handle.fileno())
            except Exception:
                try:
                    os.remove(self.lock_file)
                except OSError:
                    pass
                raise
            self.lock_token = token
            return True
        return False

    def refresh_lock(self):
        if not self.lock_token:
            return False
        snapshot = self._lock_snapshot()
        if snapshot is None or snapshot[0] != self.lock_token:
            self.lock_token = None
            return False
        try:
            os.utime(self.lock_file, None)
        except OSError:
            return False
        return True

    def release_lock(self):
        token = self.lock_token
        self.lock_token = None
        if not token:
            return
        snapshot = self._lock_snapshot()
        if snapshot is None or snapshot[0] != token:
            return
        try:
            os.remove(self.lock_file)
        except FileNotFoundError:
            pass
        except OSError:
            pass
