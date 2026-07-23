# SPDX-License-Identifier: GPL-3.0-or-later
from ..errors import SafetyError
from ..models import SelectedItem
from ..resolver import resolve_episode_context, resolve_series
from .models import RetentionReportItem


class RetentionExecutor:
    def __init__(self, manager, enumerator, logger=None):
        self.manager = manager
        self.enumerator = enumerator
        self.logger = logger

    def execute(self, candidate, policy, dry_run=False):
        stages = []
        try:
            fresh = self.enumerator.candidate_by_id(candidate.media_type, candidate.db_id)
            if not fresh:
                raise SafetyError("Candidate disappeared during revalidation")
            if fresh.arr_id != candidate.arr_id or fresh.file_id != candidate.file_id:
                raise SafetyError("Candidate identity changed during revalidation")
            stages.append("identity_revalidated")
            eligibility = policy.evaluate(fresh)
            if not eligibility.eligible:
                return RetentionReportItem(
                    fresh.media_type, fresh.display_name, fresh.db_id, False, eligibility.reason, "skipped", stages,
                )
            stages.append("eligibility_revalidated")
            if dry_run:
                return RetentionReportItem(
                    fresh.media_type, fresh.display_name, fresh.db_id, True, eligibility.reason, "dry_run", stages,
                )
            if self.manager.settings.backend != "api":
                raise SafetyError("Automatic retention requires the Servarr API deletion backend")
            if fresh.media_type == "movie":
                self._delete_movie(fresh, stages)
            elif fresh.media_type == "episode":
                self._delete_episode(fresh, stages)
            else:
                raise SafetyError("Automatic retention supports only movies and episode files")
            return RetentionReportItem(
                fresh.media_type, fresh.display_name, fresh.db_id, True, eligibility.reason, "deleted", stages,
            )
        except Exception as exc:
            if self.logger:
                self.logger.error("Retention failed for %s: %s", candidate.display_name, type(exc).__name__)
            return RetentionReportItem(
                candidate.media_type, candidate.display_name, candidate.db_id, True, "Execution failed", "failed",
                stages, type(exc).__name__,
            )

    @staticmethod
    def _selected(candidate):
        return SelectedItem(
            media_type=candidate.media_type,
            db_id=candidate.db_id,
            title=candidate.title,
            season=candidate.season,
            episode=candidate.episode,
            unique_ids=dict(candidate.unique_ids),
        )

    def _delete_movie(self, candidate, stages):
        selected = self._selected(candidate)
        plan = self.manager._plan_kodi("movie", selected)
        stages.append("kodi_sync_planned")
        self.manager.radarr.delete_movie(candidate.arr_id, delete_files=True, add_exclusion=True)
        stages.append("radarr_delete_committed")
        self.manager._sync_kodi("movie", selected, plan=plan)
        stages.append("kodi_synchronised")

    def _delete_episode(self, candidate, stages):
        selected = self._selected(candidate)
        selected.tvshow_title = candidate.display_name.split(" S", 1)[0]
        series = resolve_series(selected, self.manager.sonarr, self.manager.settings.path_mapper)
        _, linked, file_record = resolve_episode_context(selected, self.manager.sonarr, series)
        if int(file_record.get("id") or 0) != candidate.file_id:
            raise SafetyError("Episode file identity changed before deletion")
        linked_ids = [int(row.get("id") or 0) for row in linked if int(row.get("id") or 0) > 0]
        if not linked_ids:
            raise SafetyError("Sonarr returned no episodes linked to the selected file")
        original_monitored = [int(row["id"]) for row in linked if row.get("monitored")]
        plan = self.manager._plan_kodi("episodes", selected, linked)
        stages.append("kodi_sync_planned")
        if original_monitored:
            self.manager.sonarr.set_episodes_monitored(original_monitored, False)
        stages.append("linked_episodes_unmonitored")
        try:
            self.manager.sonarr.delete_episode_file(candidate.file_id)
        except Exception:
            if original_monitored:
                try:
                    self.manager.sonarr.set_episodes_monitored(original_monitored, True)
                    stages.append("monitoring_restored")
                except Exception:
                    stages.append("monitoring_restore_failed")
            raise
        stages.append("sonarr_file_delete_committed")
        self.manager._sync_kodi("episodes", selected, linked, plan=plan)
        stages.append("kodi_synchronised")
