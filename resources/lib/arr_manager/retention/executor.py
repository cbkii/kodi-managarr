# SPDX-License-Identifier: GPL-3.0-or-later
from ..errors import SafetyError
from ..models import SelectedItem, TransactionState
from ..resolver import resolve_episode_context, resolve_series
from .models import RetentionReportItem
from .policy import RetentionPolicy


class RetentionExecutor:
    def __init__(self, arr_manager, enumerator, logger=None):
        self.manager = arr_manager
        self.enumerator = enumerator
        self.logger = logger

    def execute(self, candidate, settings, dry_run=False, can_continue=None):
        eligibility = RetentionPolicy(settings).evaluate(candidate)
        if not eligibility.eligible:
            return self._item(candidate, eligibility.reason, "skipped", eligible=False)
        if dry_run:
            return self._item(candidate, eligibility.reason, "dry_run")

        tx = TransactionState(f"retention {candidate.media_type} deletion")
        try:
            fresh = self.enumerator.revalidate(candidate)
            if fresh.identity_tuple() != candidate.identity_tuple():
                raise SafetyError("Retention candidate identity changed during revalidation")
            if fresh.state_tuple() != candidate.state_tuple():
                raise SafetyError("Retention candidate watched or age state changed during revalidation")
            fresh_eligibility = RetentionPolicy(settings).evaluate(fresh)
            if not fresh_eligibility.eligible:
                raise SafetyError("Retention candidate is no longer eligible")
            if can_continue is not None and not can_continue():
                raise SafetyError("Retention run was cancelled before destructive changes")
            if fresh.media_type == "movie":
                self._delete_movie(fresh, tx)
            elif fresh.media_type == "episode":
                self._delete_episode(fresh, tx)
            else:
                raise SafetyError("Unsupported retention media type")
        except Exception as exc:
            self.manager._record_transaction(tx, exc)
            if self.logger:
                self.logger.warning(
                    "Retention deletion failed for %s1 %s",
                    candidate.stable_key,
                    type(exc).__name__,
                )
            action = "failed_after_commit" if tx.committed else "failed_before_commit"
            return self._item(
                candidate,
                eligibility.reason,
                action,
                error_type=type(exc).__name__,
                committed=tx.committed,
                stages=tx.stages,
            )

        self.manager._record_transaction(tx)
        return self._item(
            candidate,
            eligibility.reason,
            "deleted",
            committed=True,
            stages=tx.stages,
        )

    def _delete_movie(self, candidate, tx):
        selected = SelectedItem(
            media_type="movie",
            db_id=candidate.primary_kodi_id,
            title=candidate.title,
            file_path=candidate.file_path,
            unique_ids=dict(candidate.unique_ids),
        )
        kodi_plan = self.manager._plan_kodi("movie", selected)
        self.manager.radarr.delete_movie(candidate.arr_id, delete_files=True, add_exclusion=True)
        tx.mark("Radarr movie deletion and exclusion", committed=True)
        self.manager._sync_kodi("movie", selected, plan=kodi_plan)
        tx.mark("Kodi library synchronisation")

    def _delete_episode(self, candidate, tx):
        selected = SelectedItem(
            media_type="episode",
            db_id=candidate.primary_kodi_id,
            title=candidate.title,
            tvshow_title=candidate.tvshow_title,
            season=candidate.season,
            episode=candidate.episode,
            file_path=candidate.file_path,
            unique_ids=dict(candidate.unique_ids),
        )
        series = resolve_series(selected, self.manager.sonarr, self.manager.settings.path_mapper)
        _episode, linked, file_record = resolve_episode_context(selected, self.manager.sonarr, series)
        linked_ids = tuple(sorted(int(item["id"]) for item in linked))
        if int(series["id"]) != candidate.arr_id:
            raise SafetyError("Sonarr series identity changed before retention deletion")
        if int(file_record["id"]) != candidate.file_id:
            raise SafetyError("Sonarr episode-file identity changed before retention deletion")
        if linked_ids != candidate.linked_episode_ids:
            raise SafetyError("Linked Sonarr episode set changed before retention deletion")

        kodi_plan = self.manager._plan_kodi("episodes", selected, linked)
        monitored_ids = [int(item["id"]) for item in linked if item.get("monitored")]
        committed = False
        try:
            if monitored_ids:
                self.manager.sonarr.set_episodes_monitored(monitored_ids, False)
            tx.mark("episode monitoring update")
            self.manager.sonarr.delete_episode_file(candidate.file_id)
            committed = True
            tx.mark("episode file deletion", committed=True)
            self.manager._sync_kodi("episodes", selected, linked, plan=kodi_plan)
            tx.mark("Kodi library synchronisation")
        except Exception:
            if not committed and monitored_ids:
                try:
                    self.manager.sonarr.set_episodes_monitored(monitored_ids, True)
                except Exception:
                    if self.logger:
                        self.logger.exception("Could not restore episode monitoring after retention failure")
            raise

    @staticmethod
    def _item(candidate, reason, action, error_type="", committed=False, stages=None, eligible=True):
        return RetentionReportItem(
            media_type=candidate.media_type,
            display_name=candidate.display_name,
            stable_key=candidate.stable_key,
            kodi_db_ids=list(candidate.kodi_db_ids),
            arr_id=int(candidate.arr_id),
            file_id=int(candidate.file_id),
            eligible=bool(eligible),
            reason=reason,
            action_taken=action,
            error_type=error_type,
            committed=bool(committed),
            stages=list(stages or []),
        )
