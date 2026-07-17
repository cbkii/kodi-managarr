# SPDX-License-Identifier: GPL-3.0-or-later
import errno
import posixpath
import socket
import time

from .errors import ApiError, BlocklistError, SafetyError
from .fileops import make_direct_backend
from .history import unique_history_matches
from .util import is_supported_kodi_network_url, paths_equal

POLL_INTERVAL_SECONDS = 1.0


class SharedSafetyMixin:
    def _preflight_movie_backend(self, movie, file_record):
        backend = make_direct_backend(self.settings, self.logger)
        if not backend:
            return None, ""
        remote = self._remote_file_path(movie.get("path", ""), file_record)
        path = self._backend_path(remote, backend)
        if hasattr(backend, "preflight_file"):
            backend.preflight_file(path)
        return backend, path

    def _preflight_episode_backend(self, series, file_record):
        backend = make_direct_backend(self.settings, self.logger)
        if not backend:
            return None, ""
        remote = self._remote_file_path(series.get("path", ""), file_record)
        path = self._backend_path(remote, backend)
        if hasattr(backend, "preflight_file"):
            backend.preflight_file(path)
        return backend, path

    def _open_progress(self, heading, text):
        factory = getattr(self.ui, "progress", None)
        if not factory:
            return None
        return factory(heading, text)

    @staticmethod
    def _update_progress(dialog, percent, text):
        if dialog is None or not hasattr(dialog, "update"):
            return
        try:
            dialog.update(int(percent), text)
        except TypeError:
            dialog.update(int(percent))

    @staticmethod
    def _progress_cancelled(dialog):
        checker = getattr(dialog, "iscanceled", None) if dialog is not None else None
        if not checker:
            return False
        try:
            return bool(checker())
        except Exception:
            return False

    @staticmethod
    def _close_progress(dialog):
        closer = getattr(dialog, "close", None) if dialog is not None else None
        if closer:
            try:
                closer()
            except Exception:
                pass

    def _record_transaction(self, transaction, exc=None):
        recorder = getattr(self.ui, "record_transaction", None)
        if recorder:
            recorder(transaction, exc)

    def _plan_kodi(self, kind, selected, linked=None):
        if kind == "movie" and hasattr(self.ui, "plan_deleted_movie"):
            return self.ui.plan_deleted_movie(selected)
        if kind == "series" and hasattr(self.ui, "plan_deleted_series"):
            return self.ui.plan_deleted_series(selected)
        if kind == "episodes" and hasattr(self.ui, "plan_deleted_episodes"):
            return self.ui.plan_deleted_episodes(selected, linked or [])
        return None

    def _sync_kodi(self, kind, selected, linked=None, plan=None):
        try:
            if plan is not None and hasattr(self.ui, "apply_sync_plan"):
                return self.ui.apply_sync_plan(plan)
            if kind == "movie" and hasattr(self.ui, "sync_deleted_movie"):
                return self.ui.sync_deleted_movie(selected)
            if kind == "series" and hasattr(self.ui, "sync_deleted_series"):
                return self.ui.sync_deleted_series(selected)
            if kind == "episodes" and hasattr(self.ui, "sync_deleted_episodes"):
                return self.ui.sync_deleted_episodes(selected, linked or [])
            return self.ui.refresh_kodi_library()
        except Exception as exc:
            raise SafetyError(f"Kodi library synchronisation failed after deletion was committed: {exc}") from exc

    def _backend_path(self, remote_path, selected_path="", backend=None):
        del selected_path, backend
        try:
            path = self.settings.path_mapper.remote_to_kodi(remote_path)
        except ValueError as exc:
            raise SafetyError(str(exc)) from exc
        if not path:
            raise SafetyError("No allowlisted remote=>Kodi mapping was found for this destructive direct-backend path")
        for root in self.settings.path_mapper.kodi_roots:
            if paths_equal(path, root):
                raise SafetyError("Refusing to delete the configured Kodi mapping root")
        return path

    @staticmethod
    def _remote_file_path(entity_path, file_record):
        direct = file_record.get("path") or ""
        if direct.startswith("/") or is_supported_kodi_network_url(direct):
            return direct
        relative = file_record.get("relativePath") or direct
        if not entity_path or not relative:
            raise SafetyError("Servarr did not provide a complete file path")
        return posixpath.join(entity_path.rstrip("/"), str(relative).lstrip("/"))

    def _wait_for_movie_file_removed(self, movie_id, file_id):
        deadline = time.monotonic() + self.settings.poll_timeout
        last_error = None
        while time.monotonic() < deadline:
            try:
                ids = {int(row.get("id") or 0) for row in self.radarr.movie_files(movie_id)}
                last_error = None
            except Exception as exc:
                if not self._is_transient_poll_error(exc):
                    raise
                last_error = exc; self._log_transient_poll_error("Radarr movie-file reconciliation", exc)
                self._bounded_wait(POLL_INTERVAL_SECONDS); continue
            if file_id not in ids:
                return
            self._bounded_wait(POLL_INTERVAL_SECONDS)
        detail = f" Last transient error type: {type(last_error).__name__}" if last_error else ""
        raise SafetyError(f"Radarr did not clear the deleted movie file after its rescan.{detail}")

    def _wait_for_episode_files_removed(self, series_id, file_ids):
        file_ids = set(file_ids)
        deadline = time.monotonic() + self.settings.poll_timeout
        last_error = None
        while time.monotonic() < deadline:
            try:
                ids = {int(row.get("id") or 0) for row in self.sonarr.episode_files(series_id)}
                last_error = None
            except Exception as exc:
                if not self._is_transient_poll_error(exc):
                    raise
                last_error = exc; self._log_transient_poll_error("Sonarr episode-file reconciliation", exc)
                self._bounded_wait(POLL_INTERVAL_SECONDS); continue
            if not (ids & file_ids):
                return
            self._bounded_wait(POLL_INTERVAL_SECONDS)
        detail = f" Last transient error type: {type(last_error).__name__}" if last_error else ""
        raise SafetyError(f"Sonarr did not clear the deleted episode file(s) after its rescan.{detail}")

    def _blocklist_confirmation(self, matches):
        matched = unique_history_matches(matches)
        missing = sum(1 for match in matches if not match)
        if matched and missing:
            return self._m("blocklist_partial_confirm", matched=len(matched), missing=missing)
        if matched:
            return self._m("blocklist_confirm", names=", ".join(match.source_title for match in matched))
        return self._m("blocklist_none_confirm")

    def _blocklist_summary(self, matches):
        matched = unique_history_matches(matches)
        missing = sum(1 for match in matches if not match)
        if matched and missing:
            return self._m("blocklist_partial_done", matched=len(matched), missing=missing)
        if matched:
            return self._m("blocklist_done", matched=len(matched))
        return self._m("blocklist_none_done")

    def _mark_failed(self, client, history_match):
        if history_match:
            client.mark_history_failed(history_match.history_id)

    def _queue_search(self, client, response, description):
        self._poll_command(client, response, description)

    def _poll_command(self, client, response, description):
        if not isinstance(response, dict) or not response.get("id"):
            raise SafetyError(f"{description} command was not accepted by Servarr")
        command_id = int(response["id"])
        deadline = time.monotonic() + self.settings.poll_timeout
        last_error = None
        while time.monotonic() < deadline:
            try:
                state = client.command_status(command_id)
                last_error = None
            except Exception as exc:
                if not self._is_transient_poll_error(exc):
                    raise
                last_error = exc; self._log_transient_poll_error(f"{description} command polling", exc)
                self._bounded_wait(POLL_INTERVAL_SECONDS); continue
            if not isinstance(state, dict):
                raise SafetyError(f"{description} command returned a malformed status response")
            status = str(state.get("status") or "").lower()
            result = str(state.get("result") or "").lower()
            if status in {"completed", "complete"}:
                if result in {"successful", "success", "1"} or state.get("result") == 1:
                    return state
                raise SafetyError(f"{description} command completed without a successful result: {result or 'missing result'}")
            if status in {"failed", "failure", "aborted", "cancelled", "canceled", "orphaned"}:
                failure_message = state.get("message") or state.get("errorMessage") or state.get("exception") or status
                raise SafetyError(f"{description} command failed: {failure_message}")
            self._bounded_wait(POLL_INTERVAL_SECONDS)
        detail = f" Last transient error type: {type(last_error).__name__}" if last_error else ""
        raise SafetyError(f"{description} command did not complete before timeout.{detail}")

    def _is_transient_poll_error(self, exc):
        if isinstance(exc, ApiError):
            text = str(exc).lower()
            if any(token in text for token in ("invalid json", "not json", "api version", "base url", "malformed", "size limit")):
                return False
            return exc.status is None or exc.status in {408, 429} or int(exc.status or 0) >= 500
        if isinstance(exc, (socket.timeout, TimeoutError, ConnectionError)):
            return True
        if isinstance(exc, OSError):
            return getattr(exc, "errno", None) in {errno.ETIMEDOUT, errno.ECONNRESET, errno.ECONNREFUSED, errno.EHOSTUNREACH, errno.ENETUNREACH}
        return False

    def _log_transient_poll_error(self, stage, exc):
        if self.logger:
            self.logger.debug("Transient %s error; retrying until deadline: %s", stage, type(exc).__name__)

    def _bounded_wait(self, seconds):
        waiter = getattr(self.ui, "wait_for_abort", None)
        if waiter:
            if waiter(seconds):
                raise SafetyError(self._m("operation_shutting_down"))
            return
        import threading
        threading.Event().wait(seconds)

    def _require_history(self, history_match, description):
        if not history_match and self.settings.require_blocklist:
            raise BlocklistError(self._m("strict_history_missing", description=description))

    def _approved(self, heading, message, force_confirmation=False):
        if not force_confirmation and not self.settings.confirm:
            return True
        return self.ui.confirm(heading, message)
