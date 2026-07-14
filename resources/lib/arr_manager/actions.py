import os
import posixpath
import time

from .clients import RadarrClient, SonarrClient
from .errors import BlocklistError, ResolutionError, SafetyError
from .fileops import make_direct_backend
from .history import match_history, unique_history_matches
from .resolver import resolve_episode_context, resolve_movie, resolve_series
from .util import normalise_path


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
        self.ui.refresh_kodi_library()
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
        self.ui.refresh_kodi_library()
        return f"Deleted and excluded {series.get('title')}"

    def _episode_exclude(self, selected):
        series = resolve_series(selected, self.sonarr, self.settings.path_mapper)
        _, linked, file_record = resolve_episode_context(selected, self.sonarr, series)
        episode_names = ", ".join(
            f"S{int(ep.get('seasonNumber', 0)):02d}E{int(ep.get('episodeNumber', 0)):02d}" for ep in linked
        )
        message = (
            f"Delete the file for {series.get('title')} {episode_names} and unmonitor the linked episode(s)?\n\n"
            "Sonarr has no episode-level import-list exclusion; unmonitoring is the episode-level equivalent."
        )
        if not self._approved("Delete & Exclude", message):
            return "Cancelled"
        if self.settings.dry_run:
            return f"Dry run: would delete and unmonitor {episode_names}"

        originals = {int(ep["id"]): bool(ep.get("monitored", False)) for ep in linked}
        changed = []
        try:
            # Unmonitor first so a rescan cannot schedule a wanted episode during direct deletion.
            for episode in linked:
                if episode.get("monitored"):
                    updated = dict(episode)
                    updated["monitored"] = False
                    self.sonarr.update_episode(updated)
                    changed.append(episode)
            self._delete_episode_file(series, file_record, selected.file_path)
        except Exception:
            for episode in changed:
                try:
                    self.sonarr.update_episode(episode)
                except Exception:
                    self.logger.exception("Could not restore episode monitoring after failed deletion")
            raise
        self.ui.refresh_kodi_library()
        return f"Deleted and unmonitored {episode_names}"

    def _movie_replace(self, selected):
        movie = resolve_movie(selected, self.radarr, self.settings.path_mapper)
        files = self.radarr.movie_files(movie["id"])
        if len(files) != 1:
            raise ResolutionError(f"Delete & Replace requires exactly one Radarr movie file; found {len(files)}")
        file_record = files[0]
        history = self.radarr.movie_history(movie["id"], event_type=3)
        history_match = match_history(history, file_record)
        self._require_history(history_match, movie.get("title", "movie"))
        release = history_match.source_title if history_match else "no matched release"
        message = (
            f"Delete the current file for '{movie.get('title')}', blocklist '{release}', and search for a replacement?"
        )
        if not self._approved("Delete & Replace", message):
            return "Cancelled"
        if self.settings.dry_run:
            return f"Dry run: would replace {movie.get('title')} and blocklist {release}"

        self._delete_movie_file(movie, file_record, selected.file_path)
        if history_match:
            self.radarr.mark_history_failed(history_match.history_id)
        self.radarr.search_movie(movie["id"])
        self.ui.refresh_kodi_library()
        return f"Deleted and started replacement search for {movie.get('title')}"

    def _episode_replace(self, selected):
        series = resolve_series(selected, self.sonarr, self.settings.path_mapper)
        _, linked, file_record = resolve_episode_context(selected, self.sonarr, series)
        episode_ids = [int(ep["id"]) for ep in linked]
        history = self.sonarr.series_history(series["id"], selected.season, event_type=3)
        history_match = match_history(history, file_record, episode_ids)
        name = ", ".join(
            f"S{int(ep.get('seasonNumber', 0)):02d}E{int(ep.get('episodeNumber', 0)):02d}" for ep in linked
        )
        self._require_history(history_match, f"{series.get('title')} {name}")
        release = history_match.source_title if history_match else "no matched release"
        message = f"Delete {series.get('title')} {name}, blocklist '{release}', and search for a replacement?"
        if not self._approved("Delete & Replace", message):
            return "Cancelled"
        if self.settings.dry_run:
            return f"Dry run: would replace {series.get('title')} {name} and blocklist {release}"

        self._delete_episode_file(series, file_record, selected.file_path)
        if history_match:
            self.sonarr.mark_history_failed(history_match.history_id)
        self.sonarr.search_episodes(episode_ids)
        self.ui.refresh_kodi_library()
        return f"Deleted and started replacement search for {series.get('title')} {name}"

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
            raise BlocklistError(
                f"Could not match imported history for {missing} of {len(files)} episode files. Nothing was deleted."
            )
        message = (
            f"Delete all {len(files)} episode files for '{series.get('title')}', blocklist matched releases, "
            "and run a full series search?"
        )
        if not self._approved("Delete & Replace", message):
            return "Cancelled"
        if self.settings.dry_run:
            return f"Dry run: would replace all files for {series.get('title')}"

        backend = make_direct_backend(self.settings, self.logger)
        try:
            if backend is None:
                self.sonarr.delete_episode_files([record["id"] for record in files])
            else:
                for record in files:
                    remote = self._remote_file_path(series.get("path", ""), record)
                    backend.delete_file(self._backend_path(remote, "", backend))
                self.sonarr.rescan_series(series["id"])
                self._wait_for_episode_files_removed(series["id"], {int(r["id"]) for r in files})
        finally:
            if backend:
                backend.close()

        for history_match in unique_history_matches(matches):
            self.sonarr.mark_history_failed(history_match.history_id)
        self.sonarr.search_series(series["id"])
        self.ui.refresh_kodi_library()
        return f"Deleted {len(files)} files and started a series search for {series.get('title')}"

    def _delete_movie_file(self, movie, file_record, selected_path):
        backend = make_direct_backend(self.settings, self.logger)
        try:
            if backend is None:
                self.radarr.delete_movie_file(file_record["id"])
                return
            remote = self._remote_file_path(movie.get("path", ""), file_record)
            backend.delete_file(self._backend_path(remote, selected_path, backend))
            self.radarr.rescan_movie(movie["id"])
            self._wait_for_movie_file_removed(movie["id"], int(file_record["id"]))
        finally:
            if backend:
                backend.close()

    def _delete_episode_file(self, series, file_record, selected_path):
        backend = make_direct_backend(self.settings, self.logger)
        try:
            if backend is None:
                self.sonarr.delete_episode_file(file_record["id"])
                return
            remote = self._remote_file_path(series.get("path", ""), file_record)
            backend.delete_file(self._backend_path(remote, selected_path, backend))
            self.sonarr.rescan_series(series["id"])
            self._wait_for_episode_files_removed(series["id"], {int(file_record["id"])})
        finally:
            if backend:
                backend.close()

    def _backend_path(self, remote_path, selected_path, backend):
        path = self.settings.path_mapper.remote_to_kodi(remote_path)
        if not path and selected_path:
            # A selected movie/episode may already carry Kodi's authenticated SMB/SFTP VFS URL.
            path = selected_path
        if not path:
            raise SafetyError(
                "No usable file path mapping was found. Configure remote=>Kodi VFS mappings in add-on settings."
            )
        return path

    @staticmethod
    def _remote_file_path(entity_path, file_record):
        direct = file_record.get("path") or ""
        if direct.startswith("/") or direct.startswith(("smb://", "sftp://", "ssh://")):
            return direct
        relative = file_record.get("relativePath") or direct
        return posixpath.join(entity_path.rstrip("/"), str(relative).lstrip("/"))

    def _wait_for_movie_file_removed(self, movie_id, file_id):
        deadline = time.time() + self.settings.poll_timeout
        while time.time() < deadline:
            ids = {int(row.get("id") or 0) for row in self.radarr.movie_files(movie_id)}
            if file_id not in ids:
                return
            time.sleep(2)
        raise SafetyError("Radarr did not clear the deleted movie file after its rescan")

    def _wait_for_episode_files_removed(self, series_id, file_ids):
        deadline = time.time() + self.settings.poll_timeout
        while time.time() < deadline:
            ids = {int(row.get("id") or 0) for row in self.sonarr.episode_files(series_id)}
            if not (ids & set(file_ids)):
                return
            time.sleep(2)
        raise SafetyError("Sonarr did not clear the deleted episode file(s) after its rescan")

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
