# SPDX-License-Identifier: GPL-3.0-or-later
from .models import RetentionCandidate, RetentionReportItem
from ..models import SelectedItem
from ..errors import SafetyError, ResolutionError, ApiError

class RetentionExecutor:
    def __init__(self, arr_manager, kodi_client, kodi_ui, enumerator, logger):
        self.manager = arr_manager
        self.kodi = kodi_client
        self.ui = kodi_ui
        self.enumerator = enumerator
        self.logger = logger

    def revalidate_candidate(self, candidate: RetentionCandidate) -> RetentionCandidate:
        """
        Re-fetches and validates the candidate before a destructive commit.
        Ensures the candidate identity and timestamps haven't materially changed.
        """
        if candidate.media_type == "movie":
            try:
                response = self.kodi.call("VideoLibrary.GetMovieDetails", {
                    "movieid": candidate.db_id,
                    "properties": self.enumerator.MOVIE_PROPS
                })
                k_item = response.get("moviedetails")
                if not k_item:
                    raise SafetyError("Movie not found in Kodi during revalidation")
                new_candidate = self.enumerator._process_kodi_movie(k_item)
            except Exception as e:
                raise SafetyError(f"Failed to revalidate movie: {e}")

        elif candidate.media_type == "episode":
            try:
                response = self.kodi.call("VideoLibrary.GetEpisodeDetails", {
                    "episodeid": candidate.db_id,
                    "properties": self.enumerator.EPISODE_PROPS
                })
                k_item = response.get("episodedetails")
                if not k_item:
                    raise SafetyError("Episode not found in Kodi during revalidation")
                new_candidate = self.enumerator._process_kodi_episode(k_item)
            except Exception as e:
                raise SafetyError(f"Failed to revalidate episode: {e}")
        else:
            raise SafetyError("Unknown media type during revalidation")

        if not new_candidate:
             raise SafetyError("Candidate no longer valid or found in Servarr during revalidation")

        if new_candidate.arr_id != candidate.arr_id or new_candidate.file_id != candidate.file_id:
            raise SafetyError("Candidate identity changed during revalidation")

        if abs((new_candidate.date_added or 0) - (candidate.date_added or 0)) > 86400:
             raise SafetyError("Candidate addition date materially changed during revalidation")

        if new_candidate.watched != candidate.watched:
             raise SafetyError("Candidate watched state changed during revalidation")

        return new_candidate

    def execute_deletion(self, candidate: RetentionCandidate, dry_run: bool) -> RetentionReportItem:
        """
        Executes the safe deletion pipeline using Servarr APIs only.
        """
        if dry_run:
            return RetentionReportItem(
                candidate.media_type, candidate.display_name, candidate.db_id, True, "Criteria met", "dry_run"
            )

        try:
            # Revalidate fresh identity before acting
            fresh_candidate = self.revalidate_candidate(candidate)
        except SafetyError as e:
            return RetentionReportItem(
                candidate.media_type, candidate.display_name, candidate.db_id, True, "Criteria met", "failed", str(e)
            )

        try:
            if fresh_candidate.media_type == "movie":
                self._delete_movie(fresh_candidate)
            elif fresh_candidate.media_type == "episode":
                self._delete_episode(fresh_candidate)
            else:
                 raise SafetyError(f"Unsupported media type for deletion: {fresh_candidate.media_type}")

            return RetentionReportItem(
                fresh_candidate.media_type, fresh_candidate.display_name, fresh_candidate.db_id, True, "Criteria met", "deleted"
            )
        except Exception as e:
            if self.logger:
                 self.logger.error("Deletion failed for %s: %s", fresh_candidate.display_name, e)
            return RetentionReportItem(
                fresh_candidate.media_type, fresh_candidate.display_name, fresh_candidate.db_id, True, "Criteria met", "failed", str(e)
            )

    def _delete_movie(self, candidate: RetentionCandidate):
        # Movie: Delete & Exclude semantics
        # remove through Radarr, add import-list exclusion, apply targeted Kodi synchronization
        try:
            self.manager.radarr.delete_movie(candidate.arr_id, delete_files=True, add_exclusion=True)
            selected = SelectedItem("movie", db_id=candidate.db_id)
            if hasattr(self.manager, '_sync_kodi'):
                kodi_plan = self.manager._plan_kodi("movie", selected)
                self.manager._sync_kodi("movie", selected, plan=kodi_plan)
        except ApiError as e:
             raise SafetyError(f"Radarr API error: {e}") from e

    def _delete_episode(self, candidate: RetentionCandidate):
        # Episode: resolve exact file, unmonitor all linked episodes, delete file, restore monitoring if failure, sync kodi
        try:
            # Re-fetch linked episodes to ensure accuracy
            selected = SelectedItem(
                "episode", db_id=candidate.db_id, season=candidate.season, episode=candidate.episode,
                file_path=candidate.file_path, title=candidate.title
            )
            from ..resolver import resolve_series, resolve_episode_context
            series = resolve_series(selected, self.manager.sonarr, self.manager.settings.path_mapper)
            _, linked_episodes, file_record = resolve_episode_context(selected, self.manager.sonarr, series)

            if file_record['id'] != candidate.file_id:
                raise SafetyError("Episode file ID mismatch before unmonitoring")

            episode_ids = [int(ep["id"]) for ep in linked_episodes]
            original_states = {ep["id"]: ep.get("monitored", False) for ep in linked_episodes}

            # Unmonitor linked episodes
            for ep in linked_episodes:
                if ep.get("monitored"):
                    ep_copy = dict(ep)
                    ep_copy["monitored"] = False
                    self.manager.sonarr.update_episode(ep_copy)

            try:
                # Delete File
                self.manager.sonarr.delete_episode_file(candidate.file_id)
            except ApiError as e:
                # Rollback monitoring on failure
                for ep in linked_episodes:
                    if original_states.get(ep["id"]):
                         ep_copy = dict(ep)
                         ep_copy["monitored"] = True
                         try:
                             self.manager.sonarr.update_episode(ep_copy)
                         except Exception as rollback_err:
                             if self.logger:
                                 self.logger.error("Rollback failed for episode %s: %s", ep["id"], rollback_err)
                raise SafetyError(f"Sonarr API error during file deletion: {e}") from e

            if hasattr(self.manager, '_sync_kodi'):
                kodi_plan = self.manager._plan_kodi("episodes", selected, linked_episodes)
                self.manager._sync_kodi("episodes", selected, linked_episodes, plan=kodi_plan)

        except Exception as e:
             raise SafetyError(str(e)) from e
