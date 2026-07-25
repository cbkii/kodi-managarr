# SPDX-License-Identifier: GPL-3.0-or-later
from ..errors import SafetyError
from ..models import SelectedItem
from .models import RetentionReportItem


class RetentionExecutor:
    def __init__(self, arr_manager, kodi_client, enumerator, policy, logger=None):
        self.manager = arr_manager
        self.kodi = kodi_client
        self.enumerator = enumerator
        self.policy = policy
        self.logger = logger

    def execute(self, candidate, dry_run):
        if dry_run:
            return RetentionReportItem(
                candidate.media_type, candidate.display_name, candidate.db_id,
                True, "Criteria met", "dry_run",
            )
        try:
            if candidate.media_type == "movie":
                fresh = self._revalidate_movie(candidate)
                self._delete_movie(fresh)
            elif candidate.media_type == "episode":
                fresh, linked = self._revalidate_episode_file(candidate)
                self._delete_episode_file(fresh, linked)
            else:
                raise SafetyError(f"Unsupported retention media type: {candidate.media_type}")
            return RetentionReportItem(
                candidate.media_type, candidate.display_name, candidate.db_id,
                True, "Criteria met", "deleted",
            )
        except Exception as exc:
            if self.logger:
                self.logger.error("Retention deletion failed for %s: %s", candidate.display_name, exc)
            return RetentionReportItem(
                candidate.media_type, candidate.display_name, candidate.db_id,
                True, "Criteria met", "failed", str(exc),
            )

    def _revalidate_movie(self, candidate):
        result = self.kodi.call("VideoLibrary.GetMovieDetails", {
            "movieid": int(candidate.db_id),
            "properties": self.enumerator.MOVIE_PROPS,
        })
        row = result.get("moviedetails") if isinstance(result, dict) else None
        if not isinstance(row, dict):
            raise SafetyError("Movie disappeared from Kodi before retention deletion")
        fresh = self.enumerator._process_kodi_movie(row)
        if not fresh or fresh.arr_id != candidate.arr_id or fresh.file_id != candidate.file_id:
            raise SafetyError("Movie identity or file changed before retention deletion")
        if not self.policy.evaluate(fresh).eligible:
            raise SafetyError("Movie no longer satisfies the retention policy")
        return fresh

    def _revalidate_episode_file(self, candidate):
        series = self.manager.sonarr.series(candidate.arr_id)
        linked = [
            episode for episode in self.manager.sonarr.episodes(candidate.arr_id)
            if int(episode.get("episodeFileId") or 0) == int(candidate.file_id or 0)
        ]
        if not linked:
            raise SafetyError("Episode file no longer has linked Sonarr episodes")
        file_matches = [
            record for record in self.manager.sonarr.episode_files(candidate.arr_id)
            if int(record.get("id") or 0) == int(candidate.file_id or 0)
        ]
        if len(file_matches) != 1:
            raise SafetyError("Episode file identity changed before retention deletion")

        result = self.kodi.call("VideoLibrary.GetEpisodes", {
            "tvshowid": int(candidate.tvshow_db_id),
            "properties": self.enumerator.EPISODE_PROPS,
        })
        rows = result.get("episodes") if isinstance(result, dict) else None
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise SafetyError("Kodi returned malformed linked episodes before retention deletion")
        by_number = {
            (int(row.get("season", -999)), int(row.get("episode", -999))): row
            for row in rows
        }
        fresh_candidates = []
        for linked_episode in linked:
            number = (
                int(linked_episode.get("seasonNumber", -999)),
                int(linked_episode.get("episodeNumber", -999)),
            )
            row = by_number.get(number)
            if row is None:
                raise SafetyError("A linked episode is missing from Kodi; the shared file is protected")
            fresh = self.enumerator._process_kodi_episode(row)
            if not fresh or fresh.arr_id != candidate.arr_id or fresh.file_id != candidate.file_id:
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
        self.manager.radarr.delete_movie(candidate.arr_id, delete_files=True, add_exclusion=True)
        self.manager._sync_kodi("movie", selected, plan=kodi_plan)

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
            int(episode["id"]) for episode in linked
            if episode.get("monitored") and int(episode.get("id") or 0) > 0
        ]
        if monitored_ids:
            self.manager.sonarr.set_episodes_monitored(monitored_ids, False)
        committed = False
        try:
            self.manager.sonarr.delete_episode_file(candidate.file_id)
            committed = True
            self.manager._sync_kodi("episodes", selected, linked, plan=kodi_plan)
        except Exception:
            if not committed and monitored_ids:
                try:
                    self.manager.sonarr.set_episodes_monitored(monitored_ids, True)
                except Exception:
                    if self.logger:
                        self.logger.exception("Could not restore monitoring after failed retention deletion")
            raise
