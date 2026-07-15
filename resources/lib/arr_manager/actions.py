import errno
import posixpath
import socket
import time

from .clients import RadarrClient, SonarrClient
from .errors import ApiError, BlocklistError, ResolutionError, SafetyError
from .fileops import make_direct_backend
from .history import match_history, unique_history_matches
from .resolver import resolve_episode_context, resolve_movie, resolve_series
from .util import is_supported_kodi_network_url

POLL_INTERVAL_SECONDS = 1.0


class ArrManager:
    def __init__(self, settings, ui, logger):
        self.settings = settings
        self.ui = ui
        self.logger = logger
        self._radarr = None
        self._sonarr = None

    @property
    def radarr(self):
        if self._radarr is None:
            cfg = self.settings.radarr
            cfg.validate("Radarr")
            self._radarr = RadarrClient(cfg.url, cfg.api_key, cfg.api_version, cfg.timeout, cfg.verify_tls, self.logger)
        return self._radarr

    @property
    def sonarr(self):
        if self._sonarr is None:
            cfg = self.settings.sonarr
            cfg.validate("Sonarr")
            self._sonarr = SonarrClient(cfg.url, cfg.api_key, cfg.api_version, cfg.timeout, cfg.verify_tls, self.logger)
        return self._sonarr

    def execute(self, action, selected):
        if selected.media_type not in {"movie", "tvshow", "episode"}:
            raise ResolutionError(f"Unsupported Kodi item type: {selected.media_type or 'unknown'}")
        self.settings.validate_backend()
        if action == "delete_exclude":
            return self.delete_exclude(selected)
        if action == "delete_replace":
            return self.delete_replace(selected)
        raise ResolutionError(f"Unknown action: {action}")

    def delete_exclude(self, selected):
        if selected.media_type == "movie":
            return self._movie_exclude(selected)
        if selected.media_type == "tvshow":
            return self._series_exclude(selected)
        return self._episode_exclude(selected)

    def delete_replace(self, selected):
        if selected.media_type == "movie":
            return self._movie_replace(selected)
        if selected.media_type == "tvshow":
            return self._series_replace(selected)
        return self._episode_replace(selected)

    def _movie_exclude(self, selected):
        movie = resolve_movie(selected, self.radarr, self.settings.path_mapper)
        files = self.radarr.movie_files(movie["id"])
        message = (
            f"Delete '{movie.get('title')}' from Radarr, delete its {len(files)} file(s) and movie folder, "
            "and add a Radarr import-list exclusion?"
        )
        if not self._approved("Delete & Exclude", message):
            return "Cancelled"
        if self.settings.dry_run:
            return f"Dry run: would delete and exclude {movie.get('title')}"

        backend = make_direct_backend(self.settings, self.logger)
        try:
            if backend is None:
                self.radarr.delete_movie(movie["id"], delete_files=True, add_exclusion=True)
            else:
                folder = self._backend_path(movie.get("path", ""), "", backend)
                backend.delete_tree(folder)
                self.radarr.delete_movie(movie["id"], delete_files=False, add_exclusion=True)
        finally:
            if backend:
                backend.close()
        self._sync_kodi("movie", selected)
        return f"Deleted and excluded {movie.get('title')}"

    def _series_exclude(self, selected):
        series = resolve_series(selected, self.sonarr, self.settings.path_mapper)
        files = self.sonarr.episode_files(series["id"])
        message = (
            f"Delete '{series.get('title')}' from Sonarr, delete its {len(files)} episode file(s) and series folder, "
            "and add a Sonarr import-list exclusion?"
        )
        if not self._approved("Delete & Exclude", message):
            return "Cancelled"
        if self.settings.dry_run:
            return f"Dry run: would delete and exclude {series.get('title')}"

        backend = make_direct_backend(self.settings, self.logger)
        try:
            if backend is None:
                self.sonarr.delete_series(series["id"], delete_files=True, add_exclusion=True)
            else:
                folder = self._backend_path(series.get("path", ""), "", backend)
                backend.delete_tree(folder)
                self.sonarr.delete_series(series["id"], delete_files=False, add_exclusion=True)
        finally:
            if backend:
                backend.close()
        self._sync_kodi("series", selected)
        return f"Deleted and excluded {series.get('title')}"

    def _episode_exclude(self, selected):
        series = resolve_series(selected, self.sonarr, self.settings.path_mapper)
        _, linked, file_record = resolve_episode_context(selected, self.sonarr, series)
        episode_names = ", ".join(
            f"S{int(ep.get('seasonNumber', 0)):02d}E{int(ep.get('episodeNumber', 0)):02d}" for ep in linked
        )
        message = (
            f"Delete the file for {series.get('title')} {episode_names} and unmonitor the linked episode(s)?\n\n"
            "Sonarr has no episode-level import-list exclusion; unmonitoring can later be changed by Sonarr "
            "series or season monitoring actions."
        )
        if not self._approved("Delete & Exclude", message):
            return "Cancelled"
        if self.settings.dry_run:
            return f"Dry run: would delete and unmonitor {episode_names}"

        changed = []
        deletion_committed = [False]
        try:
            for episode in linked:
                if episode.get("monitored"):
                    updated = dict(episode)
                    updated["monitored"] = False
                    self.sonarr.update_episode(updated)
                    changed.append(episode)
            self._delete_episode_file(series, file_record, selected.file_path, on_committed=lambda: deletion_committed.__setitem__(0, True))
        except Exception:
            if not deletion_committed[0]:
                for episode in changed:
                    try:
                        self.sonarr.update_episode(episode)
                    except Exception:
                        if self.logger:
                            self.logger.exception("Could not restore episode monitoring after failed deletion")
            raise
        self._sync_kodi("episodes", selected, linked)
        return f"Deleted and unmonitored {episode_names}"

    def _movie_replace(self, selected):
        movie = resolve_movie(selected, self.radarr, self.settings.path_mapper)
        files = self.radarr.movie_files(movie["id"])
        if len(files) != 1:
            raise ResolutionError(f"Delete & Replace requires exactly one Radarr movie file; found {len(files)}")
        file_record = files[0]
        history_match = match_history(self.radarr.movie_history(movie["id"], event_type=3), file_record)
        self._require_history(history_match, movie.get("title", "movie"))
        release = history_match.source_title if history_match else "no matched release"
        blocklist_text = self._blocklist_confirmation([history_match])
        message = f"{blocklist_text} Delete the current file for '{movie.get('title')}' and search for a replacement?"
        if not self._approved("Delete & Replace", message):
            return "Cancelled"
        if self.settings.dry_run:
            return f"Dry run: would replace {movie.get('title')}. {self._blocklist_summary([history_match])}"

        self._mark_failed(self.radarr, history_match)
        self._delete_movie_file(movie, file_record, selected.file_path)
        self._queue_search(self.radarr, self.radarr.search_movie(movie["id"]), "Radarr movie search")
        self._sync_kodi("movie", selected)
        return f"{self._blocklist_summary([history_match])} Deleted file and started replacement search for {movie.get('title')}"

    def _episode_replace(self, selected):
        series = resolve_series(selected, self.sonarr, self.settings.path_mapper)
        _, linked, file_record = resolve_episode_context(selected, self.sonarr, series)
        episode_ids = [int(ep["id"]) for ep in linked]
        history_match = match_history(self.sonarr.series_history(series["id"], selected.season, event_type=3), file_record, episode_ids)
        name = ", ".join(f"S{int(ep.get('seasonNumber', 0)):02d}E{int(ep.get('episodeNumber', 0)):02d}" for ep in linked)
        self._require_history(history_match, f"{series.get('title')} {name}")
        release = history_match.source_title if history_match else "no matched release"
        blocklist_text = self._blocklist_confirmation([history_match])
        message = f"{blocklist_text} Delete {series.get('title')} {name} and search for a replacement?"
        if not self._approved("Delete & Replace", message):
            return "Cancelled"
        if self.settings.dry_run:
            return f"Dry run: would replace {series.get('title')} {name}. {self._blocklist_summary([history_match])}"

        self._mark_failed(self.sonarr, history_match)
        self._delete_episode_file(series, file_record, selected.file_path)
        self._queue_search(self.sonarr, self.sonarr.search_episodes(episode_ids), "Sonarr episode search")
        self._sync_kodi("episodes", selected, linked)
        return f"{self._blocklist_summary([history_match])} Deleted file and started replacement search for {series.get('title')} {name}"

    def _series_replace(self, selected):
        series = resolve_series(selected, self.sonarr, self.settings.path_mapper)
        files = self.sonarr.episode_files(series["id"])
        if not files:
            raise ResolutionError("This Sonarr series has no episode files to replace")
        episodes = self.sonarr.episodes(series["id"])
        file_episode_ids = {}
        for episode in episodes:
            file_id = int(episode.get("episodeFileId") or 0)
            if file_id:
                file_episode_ids.setdefault(file_id, []).append(int(episode["id"]))
        history = self.sonarr.series_history(series["id"], event_type=3)
        matches = [match_history(history, record, file_episode_ids.get(int(record["id"]), [])) for record in files]
        missing = sum(1 for match in matches if not match)
        if missing and self.settings.require_blocklist:
            raise BlocklistError(f"Could not match imported history for {missing} of {len(files)} episode files. Nothing was deleted.")
        matched = unique_history_matches(matches)
        message = f"{self._blocklist_confirmation(matches)} Delete all {len(files)} episode files for '{series.get('title')}' and run a full series search?"
        if not self._approved("Delete & Replace", message):
            return "Cancelled"
        if self.settings.dry_run:
            return f"Dry run: would replace all files for {series.get('title')}. {self._blocklist_summary(matches)}"

        for history_match in matched:
            self._mark_failed(self.sonarr, history_match)

        backend = make_direct_backend(self.settings, self.logger)
        try:
            if backend is None:
                self.sonarr.delete_episode_files([record["id"] for record in files])
            else:
                for record in files:
                    remote = self._remote_file_path(series.get("path", ""), record)
                    backend.delete_file(self._backend_path(remote, "", backend))
                self._poll_command(self.sonarr, self.sonarr.rescan_series(series["id"]), "Sonarr rescan")
                self._wait_for_episode_files_removed(series["id"], {int(r["id"]) for r in files})
        finally:
            if backend:
                backend.close()

        self._queue_search(self.sonarr, self.sonarr.search_series(series["id"]), "Sonarr series search")
        self._sync_kodi("episodes", selected, episodes)
        return f"{self._blocklist_summary(matches)} Deleted {len(files)} files and started a series search for {series.get('title')}"


    def _sync_kodi(self, kind, selected, linked=None):
        try:
            if kind == "movie" and hasattr(self.ui, "sync_deleted_movie"):
                return self.ui.sync_deleted_movie(selected)
            if kind == "series" and hasattr(self.ui, "sync_deleted_series"):
                return self.ui.sync_deleted_series(selected)
            if kind == "episodes" and hasattr(self.ui, "sync_deleted_episodes"):
                return self.ui.sync_deleted_episodes(selected, linked or [])
            return self.ui.refresh_kodi_library()
        except Exception as exc:
            raise SafetyError(f"Kodi library synchronisation failed after deletion was committed: {exc}") from exc

    def _delete_movie_file(self, movie, file_record, selected_path, on_committed=None):
        backend = make_direct_backend(self.settings, self.logger)
        try:
            if backend is None:
                self.radarr.delete_movie_file(file_record["id"])
                if on_committed:
                    on_committed()
                return
            remote = self._remote_file_path(movie.get("path", ""), file_record)
            backend.delete_file(self._backend_path(remote, selected_path, backend))
            if on_committed:
                on_committed()
            self._poll_command(self.radarr, self.radarr.rescan_movie(movie["id"]), "Radarr rescan")
            self._wait_for_movie_file_removed(movie["id"], int(file_record["id"]))
        finally:
            if backend:
                backend.close()

    def _delete_episode_file(self, series, file_record, selected_path, on_committed=None):
        backend = make_direct_backend(self.settings, self.logger)
        try:
            if backend is None:
                self.sonarr.delete_episode_file(file_record["id"])
                if on_committed:
                    on_committed()
                return
            remote = self._remote_file_path(series.get("path", ""), file_record)
            backend.delete_file(self._backend_path(remote, selected_path, backend))
            if on_committed:
                on_committed()
            self._poll_command(self.sonarr, self.sonarr.rescan_series(series["id"]), "Sonarr rescan")
            self._wait_for_episode_files_removed(series["id"], {int(file_record["id"])})
        finally:
            if backend:
                backend.close()

    def _backend_path(self, remote_path, selected_path, backend):
        try:
            path = self.settings.path_mapper.remote_to_kodi(remote_path)
        except ValueError as exc:
            raise SafetyError(str(exc)) from exc
        if not path:
            raise SafetyError("No allowlisted remote=>Kodi mapping was found for this destructive direct-backend path")
        return path

    @staticmethod
    def _remote_file_path(entity_path, file_record):
        direct = file_record.get("path") or ""
        if direct.startswith("/") or is_supported_kodi_network_url(direct):
            return direct
        relative = file_record.get("relativePath") or direct
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
                last_error = exc
                self._log_transient_poll_error("Radarr movie-file reconciliation", exc)
                self._bounded_wait(POLL_INTERVAL_SECONDS)
                continue
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
                last_error = exc
                self._log_transient_poll_error("Sonarr episode-file reconciliation", exc)
                self._bounded_wait(POLL_INTERVAL_SECONDS)
                continue
            if not (ids & file_ids):
                return
            self._bounded_wait(POLL_INTERVAL_SECONDS)
        detail = f" Last transient error type: {type(last_error).__name__}" if last_error else ""
        raise SafetyError(f"Sonarr did not clear the deleted episode file(s) after its rescan.{detail}")


    def _blocklist_confirmation(self, matches):
        matched = unique_history_matches(matches)
        missing = sum(1 for match in matches if not match)
        if matched and missing:
            return f"Blocklist {len(matched)} matched release(s); {missing} file(s) have no history match and may be reacquired."
        if matched:
            names = ", ".join(match.source_title for match in matched)
            return f"Blocklist matched release(s): {names}."
        return "No imported-history match will be blocklisted; the same release may be reacquired."

    def _blocklist_summary(self, matches):
        matched = unique_history_matches(matches)
        missing = sum(1 for match in matches if not match)
        if matched and missing:
            return f"Blocklisted {len(matched)} matched release(s); {missing} file(s) had no history match and may be reacquired."
        if matched:
            return f"Blocklisted {len(matched)} matched release(s)."
        return "No release was blocklisted; unmatched media may be reacquired."

    def _mark_failed(self, client, history_match):
        if history_match:
            client.mark_history_failed(history_match.history_id)

    def _queue_search(self, client, response, description):
        """Validate and poll an asynchronous Servarr search command."""
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
                last_error = exc
                self._log_transient_poll_error(f"{description} command polling", exc)
                self._bounded_wait(POLL_INTERVAL_SECONDS)
                continue
            if not isinstance(state, dict):
                raise SafetyError(f"{description} command returned a malformed status response")
            status = str(state.get("status") or "").lower()
            if status in {"completed", "complete"}:
                return state
            if status in {"failed", "failure", "aborted", "cancelled", "canceled"}:
                raise SafetyError(f"{description} command failed: {state.get('message') or state.get('errorMessage') or status}")
            self._bounded_wait(POLL_INTERVAL_SECONDS)
        detail = f" Last transient error type: {type(last_error).__name__}" if last_error else ""
        raise SafetyError(f"{description} command did not complete before timeout.{detail}")


    def _is_transient_poll_error(self, exc):
        if isinstance(exc, ApiError):
            permanent_text = str(exc).lower()
            if any(token in permanent_text for token in ("invalid json", "not json", "api version", "base url", "malformed")):
                return False
            return exc.status is None or exc.status in {408, 429} or int(exc.status or 0) >= 500
        if isinstance(exc, (socket.timeout, TimeoutError, ConnectionError)):
            return True
        if isinstance(exc, OSError):
            transient = {errno.ETIMEDOUT, errno.ECONNRESET, errno.ECONNREFUSED, errno.EHOSTUNREACH, errno.ENETUNREACH}
            return getattr(exc, "errno", None) in transient
        return False

    def _log_transient_poll_error(self, stage, exc):
        if self.logger:
            self.logger.warning("Transient %s error; retrying until deadline: %s", stage, exc)

    def _bounded_wait(self, seconds):
        waiter = getattr(self.ui, "wait_for_abort", None)
        if waiter:
            if waiter(seconds):
                raise SafetyError("Operation cancelled because Kodi is shutting down")
            return
        # Host tests do not provide xbmc.Monitor; use an interruptible event wait fallback.
        import threading
        threading.Event().wait(seconds)

    def _require_history(self, history_match, description):
        if history_match:
            return
        if self.settings.require_blocklist:
            raise BlocklistError(
                f"Could not prove which imported release created {description}. Nothing was deleted, because "
                "Require a blocklist match is enabled."
            )

    def _approved(self, heading, message):
        if not self.settings.confirm:
            return True
        return self.ui.confirm(heading, message)
