# SPDX-License-Identifier: GPL-3.0-or-later
import json
import math
import os
import secrets
import tempfile


class RetentionStateStore:
    def __init__(self, addon):
        import xbmcvfs

        self.profile = xbmcvfs.translatePath(addon.getAddonInfo("profile"))
        os.makedirs(self.profile, exist_ok=True)
        self.state_file = os.path.join(self.profile, "retention-state.json")
        self.report_file = os.path.join(self.profile, "retention-last-report.json")
        self.lock_file = os.path.join(self.profile, "retention.lock")
        self.lock_token = None
        self.lock_fd = None
        self.lock_backend = None
        self.lock_identity = None

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

    @staticmethod
    def _acquire_os_lock(descriptor):
        try:
            import fcntl
        except ImportError:
            import msvcrt

            os.lseek(descriptor, 0, os.SEEK_SET)
            try:
                msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
            except OSError:
                return None
            return "msvcrt"
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            return None
        return "fcntl"

    @staticmethod
    def _release_os_lock(descriptor, backend):
        try:
            if backend == "fcntl":
                import fcntl

                fcntl.flock(descriptor, fcntl.LOCK_UN)
            elif backend == "msvcrt":
                import msvcrt

                os.lseek(descriptor, 0, os.SEEK_SET)
                msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
        except OSError:
            pass

    @staticmethod
    def _identity(stat_result):
        return stat_result.st_dev, stat_result.st_ino

    def acquire_lock(self, stale_after=1800):
        del stale_after  # Kernel locks are released after process death; no stale stealing is needed.
        if self.lock_fd is not None:
            return False
        descriptor = None
        backend = None
        try:
            descriptor = os.open(self.lock_file, os.O_CREAT | os.O_RDWR, 0o600)
            if os.fstat(descriptor).st_size < 1:
                os.write(descriptor, b"\0")
                os.fsync(descriptor)
            backend = self._acquire_os_lock(descriptor)
            if backend is None:
                os.close(descriptor)
                return False
            descriptor_stat = os.fstat(descriptor)
            path_stat = os.stat(self.lock_file)
            if self._identity(descriptor_stat) != self._identity(path_stat):
                self._release_os_lock(descriptor, backend)
                os.close(descriptor)
                return False
            token = secrets.token_hex(16)
            os.lseek(descriptor, 0, os.SEEK_SET)
            os.ftruncate(descriptor, 0)
            os.write(descriptor, token.encode("ascii"))
            os.fsync(descriptor)
            self.lock_token = token
            self.lock_fd = descriptor
            self.lock_backend = backend
            self.lock_identity = self._identity(descriptor_stat)
            return True
        except OSError:
            if descriptor is not None:
                if backend is not None:
                    self._release_os_lock(descriptor, backend)
                try:
                    os.close(descriptor)
                except OSError:
                    pass
            return False

    def refresh_lock(self):
        if self.lock_fd is None or not self.lock_token or self.lock_identity is None:
            return False
        try:
            descriptor_stat = os.fstat(self.lock_fd)
            path_stat = os.stat(self.lock_file)
            if self._identity(descriptor_stat) != self.lock_identity:
                return False
            if self._identity(path_stat) != self.lock_identity:
                return False
            os.lseek(self.lock_fd, 0, os.SEEK_SET)
            token = os.read(self.lock_fd, 256).decode("ascii", "strict")
            if token != self.lock_token:
                return False
            os.utime(self.lock_file, None)
            os.fsync(self.lock_fd)
            return True
        except (OSError, UnicodeError):
            return False

    def release_lock(self):
        descriptor = self.lock_fd
        backend = self.lock_backend
        self.lock_token = None
        self.lock_fd = None
        self.lock_backend = None
        self.lock_identity = None
        if descriptor is None:
            return
        self._release_os_lock(descriptor, backend)
        try:
            os.close(descriptor)
        except OSError:
            pass
