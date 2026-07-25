# SPDX-License-Identifier: GPL-3.0-or-later
from ..errors import SafetyError
from ..models import SelectedItem
from .models import RetentionReportItem


class RetentionPostCommitError(SafetyError):
    """The Arr deletion committed, but a later reconciliation step failed."""


class RetentionExecutor:
    def __init__(self, arr_manager, kodi_client, enumerator, policy, logger=None):
        self.manager = arr_manager
        self.kodi = kodi_client
        self.enumerator = enumerator
        self.policy = policy
        self.logger = logger

    @staticmethod
    def _positive_id(value, description):
        try:
            result = int(value)
        except (TypeError, ValueError) as exc:
            raise SafetyError(f"{description} did not contain a positive ID") from exc
        if result <= 0:
            raise SafetyError(f"{description} did not contain a positive ID")
        return result

    @staticmethod
    def _safe_error(exc):
        if isinstance(exc, SafetyError):
            return str(exc)[:1000]
        return f"{type(exc).__name__} during retention operation; check kodi.log"

    def execute(self, candidate, dry_run):
        if dry_run:
            return RetentionReportItem(
                candidate.media_type,
                candidate.display_name,
                candidate.db_id,
                True,
                "Criteria met",
                "dry_run",
            )
        try:
            self._positive_id(candidate.db_id, "Kodi item")
            self._positive_id(candidate.arr_id, "Arr item")
            self._positive_id(candidate.file_id, "Arr media file")
            if candidate.media_type == "movie":
                fresh = self._revalidate_movie(candidate)
                self._delete_movie(fresh)
            elif candidate.media_type == "episode":
                fresh, linked = self._revalidate_episode_file(candidate)
                self._delete_episode_file(fresh, linked)
            else:
                raise SafetyError(f"Unsupported retention media type: {candidate.media_type}")
            return RetentionReportItem(
                candidate.media_type,
                candidate.display_name,
                candidate.db_id,
                True,
                "Criteria met",
                "deleted",
                committed=True,
            )
        except RetentionPostCommitError as exc:
            if self.logger:
                self.logger.exception("Retention deletion committed but reconciliation failed for %s", candidate.display_name)
            return RetentionReportItem(
                candidate.media_type,
                candidate.display_name,
                candidate.db_id,
                True,
                "Criteria met",
                "deleted_with_error",
                self._safe_error(exc),
                committed=True,
            )
        except Exception as exc:
            if self.logger:
                self.logger.exception("Retention deletion failed for %s", candidate.display_name)
            return RetentionReportItem(
                candidate.media_type,
                candidate.display_name,
                candidate.db_id,
                True,
                "Criteria met",
                "failed",
                self._safe_error(exc),
                committed=False,
            )

    def _revalidate_movie(self, candidate):
        candidate_db_id = self._positive_id(candidate.db_id, "Kodi movie")
        candidate_arr_id = self._positive_id(candidate.arr_id, "Radarr movie")
        candidate_file_id = self._positive_id(candidate.file_id, "Radarr movie file")
        result = self.kodi.call("VideoLibrary.GetMovieDetails", {
            "movieid": candidate_db_id,
            "properties": self.enumerator.MOVIE_PROPS,
        })
        row = result.get("moviedetails") if isinstance(result, dict) else None
        if not isinstance(row, dict):
            raise SafetyError("Movie disappeared from Kodi before retention deletion")
        fresh = self.enumerator._process_kodi_movie(row)
        if not fresh:
            raise SafetyError("Movie is no longer a valid retention candidate")
        fresh_arr_id = self._positive_id(fresh.arr_id, "Fresh Radarr movie")
        fresh_file_id = self._positive_id(fresh.file_id, "Fresh Radarr movie file")
        if fresh_arr_id != candidate_arr_id or fresh_file_id != candidate_file_id:
            raise SafetyError("Movie identity or file changed before retention deletion")
        if not self.policy.evaluate(fresh).eligible:
            raise SafetyError("Movie no longer satisfies the retention policy")
        return fresh

    def _revalidate_episode_file(self, candidate):
        series_id = self._positive_id(candidate.arr_id, "Sonarr series")
        file_id = self._positive_id(candidate.file_id, "Sonarr episode file")
        tvshow_id = self._positive_id(candidate.tvshow_db_id, "Kodi TV show")
        series = self.manager.sonarr.series(series_id)
        episodes = self.manager.sonarr.episodes(series_id)
        files = self.manager.sonarr.episode_files(series_id)
        linked = [
            episode for episode in episodes
            if int(episode.get("episodeFileId") or 0) == file_id
        ]
        if not linked:
            raise SafetyError("Episode file no longer has linked Sonarr episodes")
        linked_numbers = set()
        for linked_episode in linked:
            number = (
                int(linked_episode.get("seasonNumber", -999)),
                int(linked_episode.get("episodeNumber", -999)),
            )
            if number in linked_numbers:
                raise SafetyError("Sonarr returned duplicate linked episode identities")
            linked_numbers.add(number)
        file_matches = [
            record for record in files
            if int(record.get("id") or 0) == file_id
        ]
        if len(file_matches) != 1:
            raise SafetyError("Episode file identity changed before retention deletion")

        result = self.kodi.call("VideoLibrary.GetEpisodes", {
            "tvshowid": tvshow_id,
            "properties": self.enumerator.EPISODE_PROPS,
        })
        rows = result.get("episodes") if isinstance(result, dict) else None
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise SafetyError("Kodi returned malformed linked episodes before retention deletion")
        by_number = {}
        for row in rows:
            number = (int(row.get("season", -999)), int(row.get("episode", -999)))
            if number in by_number:
                raise SafetyError("Kodi returned duplicate linked episode identities")
            by_number[number] = row

        fresh_candidates = []
        snapshot = (series, episodes, files)
        for index, linked_episode in enumerate(sorted(linked, key=lambda item: (
            int(item.get("seasonNumber", -999)),
            int(item.get("episodeNumber", -999)),
        ))):
            number = (
                int(linked_episode.get("seasonNumber", -999)),
                int(linked_episode.get("episodeNumber", -999)),
            )
            row = by_number.get(number)
            if row is None:
                raise SafetyError("A linked episode is missing from Kodi; the shared file is protected")
            fresh = self.enumerator._process_kodi_episode(
                row,
                refresh=index == 0,
                sonarr_snapshot=snapshot if index == 0 else None,
            )
            if not fresh:
                raise SafetyError("A linked episode is no longer a valid retention candidate")
            fresh_arr_id = self._positive_id(fresh.arr_id, "Fresh Sonarr series")
            fresh_file_id = self._positive_id(fresh.file_id, "Fresh Sonarr episode file")
            if fresh_arr_id != series_id or fresh_file_id != file_id:
                raise SafetyError("A linked episode changed identity before retention deletion")
            if not self.policy.evaluate(fresh).eligible:
                raise SafetyError("A linked episode is protected by the retention policy")
            fresh_candidates.append(fresh)

        selected = next(
            (item for item in fresh_candidates if item.db_id == candidate.db_id),
            fresh_candidates[0],
        )
        selected.series_title = series.get("title") or selected.series_title
        return selected, linked

    def _delete_movie(self, candidate):
        selected = SelectedItem(
            media_type="movie",
            db_id=candidate.db_id,
            title=candidate.title,
            file_path=candidate.file_path,
            unique_ids=candidate.unique_ids,
        )
        kodi_plan = self.manager._plan_kodi("movie", selected)
        self.manager.radarr.delete_movie(
            self._positive_id(candidate.arr_id, "Radarr movie"),
            delete_files=True,
            add_exclusion=True,
        )
        try:
            self.manager._sync_kodi("movie", selected, plan=kodi_plan)
        except Exception as exc:
            raise RetentionPostCommitError(
                "Movie was deleted from Radarr, but Kodi reconciliation failed"
            ) from exc

    def _delete_episode_file(self, candidate, linked):
        selected = SelectedItem(
            media_type="episode",
            db_id=candidate.db_id,
            title=candidate.title,
            tvshow_title=candidate.series_title,
            tvshow_db_id=candidate.tvshow_db_id,
            season=int(candidate.season),
            episode=int(candidate.episode),
            file_path=candidate.file_path,
        )
        kodi_plan = self.manager._plan_kodi("episodes", selected, linked)
        monitored_ids = [
            self._positive_id(episode.get("id"), "Sonarr episode")
            for episode in linked
            if episode.get("monitored")
        ]
        if monitored_ids:
            self.manager.sonarr.set_episodes_monitored(monitored_ids, False)
        try:
            self.manager.sonarr.delete_episode_file(
                self._positive_id(candidate.file_id, "Sonarr episode file")
            )
        except Exception as exc:
            raise SafetyError(
                "Episode-file deletion failed after linked episodes were unmonitored; "
                "monitoring remains disabled to prevent automatic reacquisition"
            ) from exc
        try:
            self.manager._sync_kodi("episodes", selected, linked, plan=kodi_plan)
        except Exception as exc:
            raise RetentionPostCommitError(
                "Episode file was deleted from Sonarr, but Kodi reconciliation failed"
            ) from exc
