# SPDX-License-Identifier: GPL-3.0-or-later
"""Final replacement-transaction hardening layered ahead of destructive actions."""

from . import actions_destructive as destructive
from .errors import ResolutionError, SafetyError
from .models import TransactionState


class ReplacementReliabilityMixin:
    """Gate missing-file recovery and preserve precise transaction stages."""

    def _movie_replace(self, selected):
        movie = destructive.resolve_movie(selected, self.radarr, self.settings.path_mapper)
        files = self.radarr.movie_files(movie["id"])
        if not files:
            return self._recover_missing_movie(selected, movie)
        if len(files) != 1:
            raise ResolutionError(self._m("replace_one_file_required", files=len(files)))

        file_record = files[0]
        match = destructive.match_history(
            self.radarr.movie_history(movie["id"], event_type=3),
            file_record,
        )
        self._require_history(match, movie.get("title", "movie"))
        backend, path = self._preflight_movie_backend(movie, file_record)
        kodi_plan = self._plan_kodi("movie", selected)
        try:
            prompt = self._m(
                "movie_replace_confirm",
                blocklist=self._blocklist_confirmation([match]),
                title=movie.get("title"),
            )
            if not self._approved(self._m("delete_replace_heading"), prompt, backend is not None):
                return self._m("cancelled")
            if self.settings.dry_run:
                return self._m(
                    "dry_movie_replace",
                    title=movie.get("title"),
                    blocklist=self._blocklist_summary([match]),
                )

            tx = TransactionState("movie replacement")
            try:
                tx.begin("release blocklist")
                self._mark_failed(self.radarr, match)
                tx.mark("release blocklist", committed=bool(match))

                tx.begin("movie file deletion")
                if backend is None:
                    self.radarr.delete_movie_file(file_record["id"])
                else:
                    backend.delete_file(path)
                tx.mark("movie file deletion", committed=True)

                if backend:
                    tx.begin("Radarr reconciliation")
                    self._poll_command(
                        self.radarr,
                        self.radarr.rescan_movie(movie["id"]),
                        "Radarr rescan",
                    )
                    self._wait_for_movie_file_removed(movie["id"], int(file_record["id"]))
                    tx.mark("Radarr reconciliation")

                tx.begin("replacement search submission")
                command = self._queue_search(
                    self.radarr,
                    self.radarr.search_movie(movie["id"]),
                    "Radarr movie search",
                )
                tx.record_command("Radarr movie search", command)
                tx.mark("replacement search queued")

                tx.begin("Kodi library synchronisation")
                self._sync_kodi("movie", selected, plan=kodi_plan)
                tx.mark("Kodi library synchronisation")
            except Exception as exc:
                self._record_transaction(tx, exc)
                raise SafetyError(tx.failure_message(exc)) from exc
            self._record_transaction(tx)
            return self._m(
                "movie_replace_done",
                blocklist=self._blocklist_summary([match]),
                title=movie.get("title"),
            )
        finally:
            if backend:
                backend.close()

    def _recover_missing_movie(self, selected, movie):
        del selected
        prompt = self._m("movie_missing_search_confirm", title=movie.get("title"))
        if not self._approved(self._m("delete_replace_heading"), prompt):
            return self._m("cancelled")
        if self.settings.dry_run:
            return self._m("dry_movie_recovery", title=movie.get("title"))

        tx = TransactionState("movie replacement recovery")
        try:
            tx.begin("replacement search submission")
            command = self._queue_search(
                self.radarr,
                self.radarr.search_movie(movie["id"]),
                "Radarr movie search",
            )
            tx.record_command("Radarr movie search", command)
            tx.mark("replacement search queued")
        except Exception as exc:
            self._record_transaction(tx, exc)
            raise SafetyError(tx.failure_message(exc)) from exc
        self._record_transaction(tx)
        return self._m("movie_missing_search_queued", title=movie.get("title"))

    def _episode_replace(self, selected):
        series = destructive.resolve_series(selected, self.sonarr, self.settings.path_mapper)
        episode = destructive.resolve_episode(selected, self.sonarr, series)
        if int(episode.get("episodeFileId") or 0) > 0:
            return super()._episode_replace(selected)

        prompt = self._m(
            "episode_missing_search_confirm",
            title=series.get("title"),
            season=selected.season,
            episode=selected.episode,
        )
        if not self._approved(self._m("delete_replace_heading"), prompt):
            return self._m("cancelled")
        if self.settings.dry_run:
            return self._m(
                "dry_episode_recovery",
                title=series.get("title"),
                season=selected.season,
                episode=selected.episode,
            )

        tx = TransactionState("episode replacement recovery")
        try:
            tx.begin("replacement search submission")
            command = self._queue_search(
                self.sonarr,
                self.sonarr.search_episodes([int(episode["id"])]),
                "Sonarr episode search",
            )
            tx.record_command("Sonarr episode search", command)
            tx.mark("replacement search queued")
        except Exception as exc:
            self._record_transaction(tx, exc)
            raise SafetyError(tx.failure_message(exc)) from exc
        self._record_transaction(tx)
        return self._m(
            "episode_missing_search_queued",
            title=series.get("title"),
            season=selected.season,
            episode=selected.episode,
        )

    def _execute_series_replacement(
        self,
        selected,
        series,
        files,
        affected,
        kodi_plan,
        matched,
        backend,
        paths,
    ):
        tx = TransactionState("series replacement")
        progress = self._open_progress(
            self._m("delete_replace_heading"),
            self._m("progress_blocklist"),
        )
        file_ids = {int(record["id"]) for record in files}
        try:
            tx.begin("release blocklists")
            self._update_progress(progress, 5, self._m("progress_blocklist"))
            for history_match in matched:
                self._mark_failed(self.sonarr, history_match)
            tx.mark("release blocklists", committed=bool(matched))

            tx.begin("episode file deletion")
            if backend is None:
                self._update_progress(
                    progress,
                    35,
                    self._m("progress_delete", current=0, total=len(files)),
                )
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
                tx.begin("Sonarr reconciliation")
                self._update_progress(progress, 65, self._m("progress_reconcile"))
                self._poll_command(
                    self.sonarr,
                    self.sonarr.rescan_series(series["id"]),
                    "Sonarr rescan",
                )
                self._wait_for_episode_files_removed(series["id"], file_ids)
                tx.mark("Sonarr reconciliation")

            tx.begin("replacement search submission")
            self._update_progress(progress, 80, self._m("progress_search"))
            command = self._queue_search(
                self.sonarr,
                self.sonarr.search_series(series["id"]),
                "Sonarr series search",
            )
            tx.record_command("Sonarr series search", command)
            tx.mark("replacement search queued")

            tx.begin("Kodi library synchronisation")
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
