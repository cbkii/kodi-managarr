# SPDX-License-Identifier: GPL-3.0-or-later

from .errors import BlocklistError, ResolutionError, SafetyError
from .fileops import make_direct_backend
from .history import match_history, unique_history_matches
from .models import TransactionState
from .resolver import resolve_episode_context, resolve_movie, resolve_series
from .util import paths_equal


class DestructiveMixin:
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
        kodi_plan = self._plan_kodi("movie", selected)
        backend = make_direct_backend(self.settings, self.logger)
        plan = None
        try:
            if backend:
                folder = self._backend_path(movie.get("path", ""), backend)
                plan = backend.preflight_tree(folder)
            prompt = self._m("movie_exclude_confirm", title=movie.get("title"), files=len(files))
            if not self._approved(self._m("delete_exclude_heading"), prompt, backend is not None):
                return self._m("cancelled")
            if self.settings.dry_run:
                return self._m("dry_exclude", title=movie.get("title"))
            tx = TransactionState("movie delete and exclude")
            try:
                if backend is None:
                    self.radarr.delete_movie(movie["id"], delete_files=True, add_exclusion=True)
                    tx.mark("Radarr movie deletion", committed=True)
                else:
                    backend.delete_tree(plan["path"], plan)
                    tx.mark("movie folder deletion", committed=True)
                    self.radarr.delete_movie(movie["id"], delete_files=False, add_exclusion=True)
                    tx.mark("Radarr movie removal and exclusion", committed=True)
                self._sync_kodi("movie", selected, plan=kodi_plan)
                tx.mark("Kodi library synchronisation")
            except Exception as exc:
                self._record_transaction(tx, exc)
                raise SafetyError(tx.failure_message(exc)) from exc
            self._record_transaction(tx)
            return self._m("exclude_done", title=movie.get("title"))
        finally:
            if backend:
                backend.close()

    def _series_exclude(self, selected):
        series = resolve_series(selected, self.sonarr, self.settings.path_mapper)
        files = self.sonarr.episode_files(series["id"])
        kodi_plan = self._plan_kodi("series", selected)
        backend = make_direct_backend(self.settings, self.logger)
        plan = None
        try:
            if backend:
                folder = self._backend_path(series.get("path", ""), backend)
                plan = backend.preflight_tree(folder)
            prompt = self._m("series_exclude_confirm", title=series.get("title"), files=len(files))
            if not self._approved(self._m("delete_exclude_heading"), prompt, backend is not None):
                return self._m("cancelled")
            if self.settings.dry_run:
                return self._m("dry_exclude", title=series.get("title"))
            tx = TransactionState("series delete and exclude")
            try:
                if backend is None:
                    self.sonarr.delete_series(series["id"], delete_files=True, add_exclusion=True)
                    tx.mark("Sonarr series deletion", committed=True)
                else:
                    backend.delete_tree(plan["path"], plan)
                    tx.mark("series folder deletion", committed=True)
                    self.sonarr.delete_series(series["id"], delete_files=False, add_exclusion=True)
                    tx.mark("Sonarr series removal and exclusion", committed=True)
                self._sync_kodi("series", selected, plan=kodi_plan)
                tx.mark("Kodi library synchronisation")
            except Exception as exc:
                self._record_transaction(tx, exc)
                raise SafetyError(tx.failure_message(exc)) from exc
            self._record_transaction(tx)
            return self._m("exclude_done", title=series.get("title"))
        finally:
            if backend:
                backend.close()

    def _episode_exclude(self, selected):
        series = resolve_series(selected, self.sonarr, self.settings.path_mapper)
        _, linked, file_record = resolve_episode_context(selected, self.sonarr, series)
        kodi_plan = self._plan_kodi("episodes", selected, linked)
        names = ", ".join(f"S{int(ep.get('seasonNumber', 0)):02d}E{int(ep.get('episodeNumber', 0)):02d}" for ep in linked)
        backend, path = self._preflight_episode_backend(series, file_record)
        try:
            prompt = self._m("episode_exclude_confirm", title=series.get("title"), episodes=names)
            if not self._approved(self._m("delete_exclude_heading"), prompt, backend is not None):
                return self._m("cancelled")
            if self.settings.dry_run:
                return self._m("dry_episode_exclude", episodes=names)
            committed = False
            tx = TransactionState("episode delete and unmonitor")
            originally_monitored = [int(episode["id"]) for episode in linked if episode.get("monitored") and "id" in episode]
            try:
                if originally_monitored:
                    self.sonarr.set_episodes_monitored(originally_monitored, False)
                tx.mark("episode monitoring update")
                if backend is None:
                    committed = True
                    self.sonarr.delete_episode_file(file_record["id"])
                else:
                    committed = True
                    backend.delete_file(path)
                tx.mark("episode file deletion", committed=True)
                if backend:
                    self._poll_command(self.sonarr, self.sonarr.rescan_series(series["id"]), "Sonarr rescan")
                    self._wait_for_episode_files_removed(series["id"], {int(file_record["id"])})
                    tx.mark("Sonarr reconciliation")
                self._sync_kodi("episodes", selected, linked, plan=kodi_plan)
                tx.mark("Kodi library synchronisation")
            except Exception as exc:
                if not committed and originally_monitored:
                    try:
                        self.sonarr.set_episodes_monitored(originally_monitored, True)
                    except Exception:
                        if self.logger:
                            self.logger.exception("Could not restore episode monitoring after failed deletion")
                self._record_transaction(tx, exc)
                raise SafetyError(tx.failure_message(exc)) from exc
            self._record_transaction(tx)
            return self._m("episode_exclude_done", episodes=names)
        finally:
            if backend:
                backend.close()

    def _movie_replace(self, selected):
        movie = resolve_movie(selected, self.radarr, self.settings.path_mapper)
        files = self.radarr.movie_files(movie["id"])
        if len(files) != 1:
            raise ResolutionError(self._m("replace_one_file_required", files=len(files)))
        file_record = files[0]
        match = match_history(self.radarr.movie_history(movie["id"], event_type=3), file_record)
        self._require_history(match, movie.get("title", "movie"))
        backend, path = self._preflight_movie_backend(movie, file_record)
        kodi_plan = self._plan_kodi("movie", selected)
        try:
            prompt = self._m("movie_replace_confirm", blocklist=self._blocklist_confirmation([match]), title=movie.get("title"))
            if not self._approved(self._m("delete_replace_heading"), prompt, backend is not None):
                return self._m("cancelled")
            if self.settings.dry_run:
                return self._m("dry_movie_replace", title=movie.get("title"), blocklist=self._blocklist_summary([match]))
            tx = TransactionState("movie replacement")
            try:
                self._mark_failed(self.radarr, match); tx.mark("release blocklist", committed=bool(match))
                if backend is None:
                    self.radarr.delete_movie_file(file_record["id"])
                else:
                    backend.delete_file(path)
                tx.mark("movie file deletion", committed=True)
                if backend:
                    self._poll_command(self.radarr, self.radarr.rescan_movie(movie["id"]), "Radarr rescan")
                    self._wait_for_movie_file_removed(movie["id"], int(file_record["id"]))
                    tx.mark("Radarr reconciliation")
                self._queue_search(self.radarr, self.radarr.search_movie(movie["id"]), "Radarr movie search")
                tx.mark("replacement search")
                self._sync_kodi("movie", selected, plan=kodi_plan); tx.mark("Kodi library synchronisation")
            except Exception as exc:
                self._record_transaction(tx, exc)
                raise SafetyError(tx.failure_message(exc)) from exc
            self._record_transaction(tx)
            return self._m("movie_replace_done", blocklist=self._blocklist_summary([match]), title=movie.get("title"))
        finally:
            if backend:
                backend.close()

    def _episode_replace(self, selected):
        series = resolve_series(selected, self.sonarr, self.settings.path_mapper)
        _, linked, file_record = resolve_episode_context(selected, self.sonarr, series)
        episode_ids = [int(ep["id"]) for ep in linked]
        match = match_history(self.sonarr.series_history(series["id"], selected.season, event_type=3), file_record, episode_ids)
        name = ", ".join(f"S{int(ep.get('seasonNumber', 0)):02d}E{int(ep.get('episodeNumber', 0)):02d}" for ep in linked)
        self._require_history(match, f"{series.get('title')} {name}")
        backend, path = self._preflight_episode_backend(series, file_record)
        kodi_plan = self._plan_kodi("episodes", selected, linked)
        try:
            prompt = self._m("episode_replace_confirm", blocklist=self._blocklist_confirmation([match]), title=series.get("title"), episodes=name)
            if not self._approved(self._m("delete_replace_heading"), prompt, backend is not None):
                return self._m("cancelled")
            if self.settings.dry_run:
                return self._m("dry_episode_replace", title=series.get("title"), episodes=name, blocklist=self._blocklist_summary([match]))
            tx = TransactionState("episode replacement")
            try:
                self._mark_failed(self.sonarr, match); tx.mark("release blocklist", committed=bool(match))
                if backend is None:
                    self.sonarr.delete_episode_file(file_record["id"])
                else:
                    backend.delete_file(path)
                tx.mark("episode file deletion", committed=True)
                if backend:
                    self._poll_command(self.sonarr, self.sonarr.rescan_series(series["id"]), "Sonarr rescan")
                    self._wait_for_episode_files_removed(series["id"], {int(file_record["id"])})
                    tx.mark("Sonarr reconciliation")
                self._queue_search(self.sonarr, self.sonarr.search_episodes(episode_ids), "Sonarr episode search")
                tx.mark("replacement search")
                self._sync_kodi("episodes", selected, linked, plan=kodi_plan); tx.mark("Kodi library synchronisation")
            except Exception as exc:
                self._record_transaction(tx, exc)
                raise SafetyError(tx.failure_message(exc)) from exc
            self._record_transaction(tx)
            return self._m("episode_replace_done", blocklist=self._blocklist_summary([match]), title=series.get("title"), episodes=name)
        finally:
            if backend:
                backend.close()

    def _resolve_series_replacement_plan(self, selected):
        series = resolve_series(selected, self.sonarr, self.settings.path_mapper)
        files = self.sonarr.episode_files(series["id"])
        if not files:
            raise ResolutionError(self._m("series_no_files"))
        episodes = self.sonarr.episodes(series["id"])
        file_ids = {int(record["id"]) for record in files}
        affected = [episode for episode in episodes if int(episode.get("episodeFileId") or 0) in file_ids]
        kodi_plan = self._plan_kodi("episodes", selected, affected)
        file_episode_ids = {}
        for episode in affected:
            file_episode_ids.setdefault(int(episode.get("episodeFileId") or 0), []).append(int(episode["id"]))
        history = self.sonarr.series_history(series["id"], event_type=3)
        matches = [match_history(history, record, file_episode_ids.get(int(record["id"]), [])) for record in files]
        missing = sum(1 for match in matches if not match)
        if missing and self.settings.require_blocklist:
            raise BlocklistError(self._m("series_history_missing", missing=missing, files=len(files)))
        return series, files, affected, kodi_plan, matches, unique_history_matches(matches)

    def _preflight_direct_replacement_targets(self, series, files, backend):
        paths = []
        if backend is None:
            return paths
        preflight_progress = self._open_progress(
            self._m("delete_replace_heading"),
            self._m("progress_preflight", current=0, total=len(files)),
        )
        try:
            for index, record in enumerate(files, start=1):
                self._update_progress(
                    preflight_progress,
                    int(index / max(len(files), 1) * 100),
                    self._m("progress_preflight", current=index, total=len(files)),
                )
                if self._progress_cancelled(preflight_progress):
                    raise SafetyError(self._m("cancelled_precommit"))
                remote = self._remote_file_path(series.get("path", ""), record)
                path = self._backend_path(remote, backend)
                if any(paths_equal(path, existing) for existing in paths):
                    raise SafetyError("Multiple Sonarr file records resolved to the same direct-delete target")
                if hasattr(backend, "preflight_file"):
                    backend.preflight_file(path)
                paths.append(path)
        finally:
            self._close_progress(preflight_progress)
        return paths

    def _execute_series_replacement(self, selected, series, files, affected, kodi_plan, matched, backend, paths):
        tx = TransactionState("series replacement")
        progress = self._open_progress(self._m("delete_replace_heading"), self._m("progress_blocklist"))
        file_ids = {int(record["id"]) for record in files}
        try:
            self._update_progress(progress, 5, self._m("progress_blocklist"))
            for history_match in matched:
                self._mark_failed(self.sonarr, history_match)
            tx.mark("release blocklists", committed=bool(matched))
            if backend is None:
                self._update_progress(progress, 35, self._m("progress_delete", current=0, total=len(files)))
                self.sonarr.delete_episode_files([record["id"] for record in files])
                tx.mark("episode file deletion", committed=True)
            else:
                for index, path in enumerate(paths, start=1):
                    self._update_progress(
                        progress,
                        10 + int(index / max(len(paths), 1) * 50),
                        self._m("progress_delete", current=index, total=len(paths)),
                    )
                    backend.delete_file(path)
                    tx.mark(f"episode file deletion {index}/{len(paths)}", committed=True)
                self._update_progress(progress, 65, self._m("progress_reconcile"))
                self._poll_command(self.sonarr, self.sonarr.rescan_series(series["id"]), "Sonarr rescan")
                self._wait_for_episode_files_removed(series["id"], file_ids)
                tx.mark("Sonarr reconciliation")
            self._update_progress(progress, 80, self._m("progress_search"))
            self._queue_search(self.sonarr, self.sonarr.search_series(series["id"]), "Sonarr series search")
            tx.mark("replacement search")
            self._update_progress(progress, 95, self._m("progress_kodi"))
            self._sync_kodi("episodes", selected, affected, plan=kodi_plan)
            tx.mark("Kodi library synchronisation")
            self._update_progress(progress, 100, self._m("progress_kodi"))
        except Exception as exc:
            self._record_transaction(tx, exc)
            raise SafetyError(tx.failure_message(exc)) from exc
        finally:
            self._close_progress(progress)
        self._record_transaction(tx)

    def _series_replace(self, selected):
        series, files, affected, kodi_plan, matches, matched = self._resolve_series_replacement_plan(selected)
        backend = make_direct_backend(self.settings, self.logger)
        try:
            paths = self._preflight_direct_replacement_targets(series, files, backend)
            prompt = self._m(
                "series_replace_confirm",
                blocklist=self._blocklist_confirmation(matches),
                files=len(files),
                title=series.get("title"),
            )
            if not self._approved(self._m("delete_replace_heading"), prompt, backend is not None):
                return self._m("cancelled")
            if self.settings.dry_run:
                return self._m(
                    "dry_series_replace",
                    title=series.get("title"),
                    blocklist=self._blocklist_summary(matches),
                )
            self._execute_series_replacement(selected, series, files, affected, kodi_plan, matched, backend, paths)
            return self._m(
                "series_replace_done",
                blocklist=self._blocklist_summary(matches),
                files=len(files),
                title=series.get("title"),
            )
        finally:
            if backend:
                backend.close()
