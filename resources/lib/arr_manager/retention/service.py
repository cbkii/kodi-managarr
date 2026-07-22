# SPDX-License-Identifier: GPL-3.0-or-later
import time
from datetime import datetime, timezone

from ..actions import ArrManager
from ..config import Settings
from ..errors import ConfigurationError, SafetyError
from ..messages import message
from ..pin import pin_policy_generation, pin_policy_generation_from_addon
from .config import RetentionSettings
from .enumerator import RetentionEnumerator
from .executor import RetentionExecutor
from .policy import RetentionPolicy
from .models import RetentionReportItem
from .reports import RetentionStateStore


def _utc_text(timestamp=None):
    value = float(timestamp if timestamp is not None else time.time())
    return datetime.fromtimestamp(value, timezone.utc).isoformat().replace("+00:00", "Z")


class RetentionService:
    PREVIEW_DISPLAY_LIMIT = 25

    def __init__(
        self,
        arr_manager,
        kodi_client,
        kodi_ui=None,
        logger=None,
        state_store=None,
        addon=None,
    ):
        if arr_manager is None and addon is None:
            raise ValueError("RetentionService requires an add-on or ArrManager")
        self.manager = arr_manager
        self.kodi = kodi_client
        self.ui = kodi_ui
        self.logger = logger
        self.addon = addon or arr_manager.settings.addon
        self.store = state_store or RetentionStateStore(self.addon, logger)

    def _m(self, key, **values):
        return message(self.addon, key, **values)

    def _reason_text(self, reason, eligibility=None):
        mapping = {
            "not_watched": "retention_reason_not_watched",
            "no_criteria": "retention_reason_no_criteria",
            "criteria_not_all_met": "retention_reason_all",
            "criteria_none_met": "retention_reason_any",
            "recently_committed": "retention_reason_recent",
            "movie_without_single_file": "retention_reason_movie_file",
            "movie_unmanaged_or_ambiguous": "retention_reason_movie_match",
            "movie_invalid": "retention_reason_movie_invalid",
            "episode_without_file": "retention_reason_episode_file",
            "episode_unmanaged_or_ambiguous": "retention_reason_episode_match",
            "episode_invalid": "retention_reason_episode_invalid",
        }
        if reason == "eligible" and eligibility is not None:
            unavailable = self._m("retention_age_unavailable")
            return self._m(
                "retention_reason_eligible",
                added=(eligibility.added_age_days if eligibility.added_age_days is not None else unavailable),
                watched=(eligibility.watched_age_days if eligibility.watched_age_days is not None else unavailable),
            )
        return self._m(mapping.get(reason, "retention_reason_unknown"))

    def _action_text(self, action):
        mapping = {
            "preview": "retention_action_preview",
            "deleted": "retention_action_deleted",
            "dry_run": "retention_action_dry_run",
            "skipped": "retention_action_skipped",
            "failed_before_commit": "retention_action_failed_before",
            "failed_after_commit": "retention_action_failed_after",
        }
        return self._m(mapping.get(action, "retention_action_skipped"))

    @staticmethod
    def _periodic_enabled(addon):
        return addon.getSetting("retention_periodic_enabled").strip().lower() in {
            "1", "true", "yes", "on",
        }

    def _components(self):
        # The Kodi service is long-lived. Reload the complete add-on settings and
        # rebuild Servarr clients for every pass so PIN, backend and credentials
        # cannot remain stale after an in-Kodi settings change.
        full_settings = Settings(self.addon)
        if self.logger:
            self.logger.debug_enabled = full_settings.debug
        settings = full_settings.retention.validate()
        self.manager = ArrManager(full_settings, self.ui, self.logger)
        enumerator = RetentionEnumerator(
            self.kodi,
            self.manager,
            full_settings.path_mapper,
            self.logger,
        )
        executor = RetentionExecutor(self.manager, enumerator, self.logger)
        return settings, enumerator, executor

    def _scan(self, settings, enumerator, keep_limit=None, recent_keys=None):
        policy = RetentionPolicy(settings)
        recent_keys = set(recent_keys or ())
        eligible = []
        eligible_details = []
        eligible_count = 0
        scanned_count = 0
        skipped_reasons = {}
        for scan in enumerator.iter_scan_results(settings):
            scanned_count += 1
            if scan.candidate is None:
                reason = scan.skipped_reason or "unresolved"
                skipped_reasons[reason] = skipped_reasons.get(reason, 0) + 1
                continue
            candidate = scan.candidate
            if candidate.stable_key in recent_keys:
                skipped_reasons["recently_committed"] = skipped_reasons.get("recently_committed", 0) + 1
                continue
            eligibility = policy.evaluate(candidate)
            if not eligibility.eligible:
                skipped_reasons[eligibility.reason] = skipped_reasons.get(eligibility.reason, 0) + 1
                continue
            eligible_count += 1
            if keep_limit is None or len(eligible) < keep_limit:
                eligible.append(candidate)
                eligible_details.append((candidate, eligibility))
        return {
            "scanned": scanned_count,
            "eligible_count": eligible_count,
            "eligible": eligible,
            "eligible_details": eligible_details,
            "skipped_reasons": skipped_reasons,
        }

    def run_preview(self):
        settings, enumerator, _executor = self._components()
        result = self._scan(settings, enumerator, keep_limit=self.PREVIEW_DISPLAY_LIMIT)
        lines = [
            self._m(
                "retention_preview_summary",
                eligible=result["eligible_count"],
                scanned=result["scanned"],
                limit=settings.max_deletions,
                dry_run=self._m("enabled") if self.manager.settings.dry_run else self._m("disabled"),
            )
        ]
        if result["eligible_details"]:
            lines.append("")
            lines.extend(
                "- " + self._m(
                    "retention_preview_item",
                    name=candidate.display_name,
                    reason=self._reason_text(eligibility.reason, eligibility),
                )
                for candidate, eligibility in result["eligible_details"]
            )
            hidden = result["eligible_count"] - len(result["eligible"])
            if hidden > 0:
                lines.append(self._m("retention_more_items", count=hidden))
        if result["skipped_reasons"]:
            lines.append("")
            lines.append(self._m("retention_skipped_heading"))
            for reason, count in sorted(result["skipped_reasons"].items()):
                lines.append(f"- {count}: {self._reason_text(reason)}")
        text = "\n".join(lines)
        if self.ui:
            self.ui.text(self._m("retention_preview_heading"), text)
        preview_items = [
            RetentionReportItem(
                media_type=candidate.media_type,
                display_name=candidate.display_name,
                stable_key=candidate.stable_key,
                kodi_db_ids=list(candidate.kodi_db_ids),
                arr_id=candidate.arr_id,
                file_id=candidate.file_id,
                eligible=True,
                reason=self._reason_text(eligibility.reason, eligibility),
                action_taken="preview",
            )
            for candidate, eligibility in result["eligible_details"]
        ]
        self._save_report(
            "preview",
            self.manager.settings.dry_run,
            result,
            preview_items,
            started=time.time(),
            completed=time.time(),
        )
        return result

    def run_cleanup_now(self, authorized=False):
        settings, enumerator, executor = self._components()
        dry_run = bool(self.manager.settings.dry_run)
        if not dry_run and not authorized:
            raise SafetyError("Real retention cleanup was not authorised")
        if not self.store.acquire_lock(stale_after_seconds=3600):
            if self.ui:
                self.ui.ok(self._m("retention_heading"), self._m("retention_already_running"))
            return {"status": "locked", "deleted": 0, "failed": 0}

        started = time.time()
        try:
            scan = self._scan(settings, enumerator, keep_limit=settings.max_deletions)
            if not scan["eligible"]:
                if self.ui:
                    self.ui.ok(self._m("retention_heading"), self._m("retention_no_eligible"))
                self._save_report("manual", dry_run, scan, [], started, time.time())
                return {"status": "no_eligible", "deleted": 0, "failed": 0}

            count = min(scan["eligible_count"], settings.max_deletions)
            prompt = self._m(
                "retention_run_confirm",
                count=count,
                mode=self._m("retention_dry_run_mode") if dry_run else self._m("retention_real_mode"),
            )
            if self.ui and not self.ui.confirm(self._m("retention_heading"), prompt):
                return {"status": "cancelled", "deleted": 0, "failed": 0}

            results = self._execute_candidates(
                scan["eligible"],
                settings,
                executor,
                dry_run=dry_run,
                interactive=True,
            )
            completed = time.time()
            summary = self._summarise(results)
            self._save_report("manual", dry_run, scan, results, started, completed)
            if self.ui:
                self.ui.ok(
                    self._m("retention_complete_heading"),
                    self._m(
                        "retention_complete_summary",
                        deleted=summary["deleted"],
                        dry_run=summary["dry_run"],
                        failed=summary["failed"],
                        skipped=summary["skipped"],
                    ),
                )
            return {"status": "completed", **summary}
        finally:
            self.store.release_lock()

    def enable_periodic(self, authorized=False):
        settings, _enumerator, _executor = self._components()
        if not settings.background_dry_run and not authorized:
            raise SafetyError("Real periodic retention was not authorised")
        now = time.time()
        state = self.store.load_state()
        state.update({
            "auth_generation": pin_policy_generation(self.manager.settings),
            "real_authorized": bool(not settings.background_dry_run and authorized),
            "next_due": now + settings.interval_hours * 3600,
            "last_enabled": _utc_text(now),
        })
        self.store.save_state(state)
        self.addon.setSetting("retention_periodic_enabled", "true")
        if self.ui:
            self.ui.notification(self._m("retention_periodic_enabled"))
        return state

    def disable_periodic(self):
        state = self.store.load_state()
        state.update({
            "auth_generation": "",
            "real_authorized": False,
            "next_due": 0,
            "last_disabled": _utc_text(),
        })
        self.store.save_state(state)
        self.addon.setSetting("retention_periodic_enabled", "false")
        if self.ui:
            self.ui.notification(self._m("retention_periodic_disabled"))
        return state

    def run_background(self, abort_checker=None):
        try:
            settings, enumerator, executor = self._components()
        except ConfigurationError as exc:
            self._log_background_error(exc)
            return {"status": "disabled_or_invalid"}
        if not settings.periodic_enabled:
            return {"status": "disabled"}

        now = time.time()
        state = self.store.load_state()
        try:
            next_due = float(state.get("next_due") or 0)
        except (TypeError, ValueError):
            next_due = 0
        if now < next_due:
            return {"status": "not_due", "next_due": next_due}
        if not self.store.acquire_lock(stale_after_seconds=max(3600, settings.interval_hours * 3600)):
            return {"status": "locked"}

        started = time.time()
        try:
            # Re-read settings and state only after owning the lock so concurrent
            # settings/manual changes cannot race the checks below.
            settings, enumerator, executor = self._components()
            state = self.store.load_state()
            if not settings.periodic_enabled:
                return {"status": "disabled"}
            try:
                locked_next_due = float(state.get("next_due") or 0)
            except (TypeError, ValueError):
                locked_next_due = 0
            if time.time() < locked_next_due:
                return {"status": "not_due", "next_due": locked_next_due}
            dry_run = bool(settings.background_dry_run)
            generation = pin_policy_generation(self.manager.settings)
            if not dry_run and not (
                bool(state.get("real_authorized"))
                and str(state.get("auth_generation") or "") == generation
            ):
                self.addon.setSetting("retention_periodic_enabled", "false")
                state.update({
                    "real_authorized": False,
                    "next_due": 0,
                    "last_completed": _utc_text(),
                })
                self.store.save_state(state)
                report = self._error_report(
                    "scheduled",
                    dry_run,
                    started,
                    "RetentionAuthorizationError",
                )
                self.store.save_report(report)
                self._background_notification(settings, 0, 1)
                return {"status": "authorization_stale"}

            recent = {
                str(item.get("key") or "")
                for item in state.get("recent_processed", [])
                if isinstance(item, dict)
            }
            scan = self._scan(
                settings,
                enumerator,
                keep_limit=settings.max_deletions,
                recent_keys=recent,
            )

            def can_continue():
                if abort_checker and abort_checker():
                    return False
                if not self._periodic_enabled(self.addon):
                    return False
                if self.addon.getSetting("retention_enabled").strip().lower() not in {
                    "1", "true", "yes", "on",
                }:
                    return False
                if not dry_run and pin_policy_generation_from_addon(self.addon) != generation:
                    return False
                return True

            results = self._execute_candidates(
                scan["eligible"],
                settings,
                executor,
                dry_run=dry_run,
                interactive=False,
                can_continue=can_continue,
            )
            completed = time.time()
            summary = self._summarise(results)
            authorization_current = dry_run or pin_policy_generation_from_addon(self.addon) == generation
            periodic_current = self._periodic_enabled(self.addon)
            if not authorization_current:
                self.addon.setSetting("retention_periodic_enabled", "false")
            processed = list(state.get("recent_processed", []))
            processed.extend(
                {"key": item.stable_key, "time": completed}
                for item in results
                if item.committed
            )
            state.update({
                "auth_generation": generation if authorization_current else "",
                "real_authorized": bool(not dry_run and authorization_current),
                "last_started": _utc_text(started),
                "last_completed": _utc_text(completed),
                "next_due": (
                    completed + settings.interval_hours * 3600
                    if authorization_current and periodic_current else 0
                ),
                "recent_processed": processed,
            })
            self.store.save_state(state)
            self._save_report("scheduled", dry_run, scan, results, started, completed)
            self._background_notification(settings, summary["deleted"], summary["failed"])
            if not authorization_current:
                return {"status": "authorization_changed", **summary}
            if not periodic_current:
                return {"status": "disabled_during_run", **summary}
            return {"status": "completed", **summary}
        except Exception as exc:
            completed = time.time()
            state.update({
                "last_started": _utc_text(started),
                "last_completed": _utc_text(completed),
                "next_due": completed + settings.interval_hours * 3600,
            })
            self.store.save_state(state)
            self.store.save_report(
                self._error_report("scheduled", settings.background_dry_run, started, type(exc).__name__)
            )
            self._log_background_error(exc)
            self._background_notification(settings, 0, 1)
            return {"status": "failed", "error_type": type(exc).__name__}
        finally:
            self.store.release_lock()

    def view_report(self):
        report = self.store.load_report()
        if not report:
            if self.ui:
                self.ui.ok(self._m("retention_report_heading"), self._m("retention_no_report"))
            return report
        counts = report.get("counts", {}) if isinstance(report.get("counts"), dict) else {}
        lines = [
            self._m(
                "retention_report_header",
                run_type=report.get("run_type", "unknown"),
                dry_run=report.get("dry_run", False),
                started=report.get("started", ""),
                completed=report.get("completed", ""),
                next_due=report.get("next_due", ""),
            ),
            self._m(
                "retention_report_counts",
                eligible=counts.get("eligible", 0),
                processed=counts.get("processed", 0),
                deleted=counts.get("deleted", 0),
                dry_run=counts.get("dry_run", 0),
                failed=counts.get("failed", 0),
                skipped=counts.get("skipped", 0),
            ),
        ]
        for item in report.get("items", []):
            if not isinstance(item, dict):
                continue
            error = (
                self._m("retention_error_suffix", error_type=item["error_type"])
                if item.get("error_type") else ""
            )
            lines.append(
                "- " + self._m(
                    "retention_report_item",
                    name=item.get("display_name", ""),
                    action=self._action_text(item.get("action", "")),
                    error=error,
                )
            )
        if self.ui:
            self.ui.text(self._m("retention_report_heading"), "\n".join(lines))
        return report

    def _execute_candidates(
        self,
        candidates,
        settings,
        executor,
        dry_run,
        interactive,
        can_continue=None,
    ):
        results = []
        dialog = None
        if interactive and self.ui:
            dialog = self.ui.progress(self._m("retention_heading"), self._m("retention_progress"))
        try:
            total = max(len(candidates), 1)
            for index, candidate in enumerate(candidates):
                if dialog is not None:
                    checker = getattr(dialog, "iscanceled", None)
                    if checker and checker():
                        break
                    updater = getattr(dialog, "update", None)
                    if updater:
                        updater(int(index / total * 100), candidate.display_name)
                if can_continue is not None and not can_continue():
                    break
                item = executor.execute(
                    candidate,
                    settings,
                    dry_run=dry_run,
                    can_continue=can_continue,
                )
                results.append(item)
        finally:
            closer = getattr(dialog, "close", None) if dialog is not None else None
            if closer:
                try:
                    closer()
                except Exception:
                    if self.logger:
                        self.logger.warning("Could not close retention progress dialog")
        return results

    @staticmethod
    def _summarise(results):
        return {
            "deleted": sum(item.action_taken == "deleted" for item in results),
            "dry_run": sum(item.action_taken == "dry_run" for item in results),
            "failed": sum(item.action_taken.startswith("failed") for item in results),
            "skipped": sum(item.action_taken == "skipped" for item in results),
        }

    def _save_report(self, run_type, dry_run, scan, results, started, completed):
        summary = self._summarise(results)
        state = self.store.load_state()
        try:
            next_due_value = float(state.get("next_due") or 0)
        except (TypeError, ValueError):
            next_due_value = 0
        unresolved_skipped = sum(int(value) for value in scan.get("skipped_reasons", {}).values())
        payload = {
            "schema": 1,
            "run_type": run_type,
            "dry_run": bool(dry_run),
            "started": _utc_text(started),
            "completed": _utc_text(completed),
            "next_due": _utc_text(next_due_value) if next_due_value > 0 else "",
            "counts": {
                "scanned": int(scan.get("scanned", 0)),
                "eligible": int(scan.get("eligible_count", 0)),
                "processed": len(results),
                **summary,
                "skipped": summary["skipped"] + unresolved_skipped,
            },
            "skipped_reasons": dict(scan.get("skipped_reasons", {})),
            "items": [
                {
                    "media_type": item.media_type,
                    "display_name": item.display_name,
                    "stable_key": item.stable_key,
                    "kodi_db_ids": list(item.kodi_db_ids),
                    "arr_id": item.arr_id,
                    "file_id": item.file_id,
                    "action": item.action_taken,
                    "reason": (
                        item.reason if item.action_taken == "preview"
                        else self._reason_text(item.reason)
                    ),
                    "error_type": item.error_type,
                    "committed": item.committed,
                    "stages": list(item.stages),
                }
                for item in results
            ],
        }
        self.store.save_report(payload)

    @staticmethod
    def _error_report(run_type, dry_run, started, error_type):
        return {
            "schema": 1,
            "run_type": run_type,
            "dry_run": bool(dry_run),
            "started": _utc_text(started),
            "completed": _utc_text(),
            "next_due": "",
            "counts": {"scanned": 0, "eligible": 0, "processed": 0, "deleted": 0, "dry_run": 0, "failed": 1, "skipped": 0},
            "skipped_reasons": {},
            "items": [{"action": "failed", "error_type": error_type, "committed": False, "stages": []}],
        }

    def _background_notification(self, settings, deleted, failed):
        if not self.ui or settings.notification_mode == "silent":
            return
        if settings.notification_mode == "errors_only" and not failed:
            return
        if settings.notification_mode == "deletions_and_errors" and not (deleted or failed):
            return
        self.ui.notification(
            self._m("retention_background_summary", deleted=deleted, failed=failed),
            error=bool(failed),
        )

    def _log_background_error(self, exc):
        if self.logger:
            self.logger.error("Retention background pass failed: %s", type(exc).__name__)
