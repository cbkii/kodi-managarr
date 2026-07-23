# SPDX-License-Identifier: GPL-3.0-or-later
import time
from datetime import datetime, timezone

from ..actions import ArrManager
from ..errors import ConfigurationError, ResolutionError, SafetyError
from ..pin import authorize_action, pin_policy_generation
from ..resolver import resolve_movie, resolve_series
from ..util import as_int
from .config import RetentionSettings
from .enumerator import RetentionEnumerator
from .exclusions import RetentionExclusions
from .executor import RetentionExecutor
from .policy import RetentionPolicy
from .state import RetentionStateStore


class RetentionController:
    PREVIEW_LIMIT = 40

    def __init__(self, addon, settings, ui, logger):
        import xbmcvfs
        self.addon = addon
        self.settings = settings
        self.ui = ui
        self.logger = logger
        self.manager = ArrManager(settings, ui, logger)
        self.profile = xbmcvfs.translatePath(addon.getAddonInfo("profile"))
        self.exclusions = RetentionExclusions(self.profile)
        self.state = RetentionStateStore(self.profile)
        self.enumerator = RetentionEnumerator(ui.jsonrpc, self.manager, settings.path_mapper, logger)
        self.executor = RetentionExecutor(self.manager, self.enumerator, logger)

    def _retention_settings(self, require_enabled=True):
        value = RetentionSettings.from_addon(self.addon)
        value.validate(require_enabled=require_enabled)
        return value

    @staticmethod
    def _iso(timestamp=None):
        return datetime.fromtimestamp(timestamp or time.time(), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    @staticmethod
    def _item_line(candidate, eligibility):
        rating = f", rating {candidate.rating:.1f}" if candidate.rating is not None else ""
        ages = []
        if eligibility.added_age_days is not None:
            ages.append(f"added {eligibility.added_age_days}d")
        if eligibility.watched_age_days is not None:
            ages.append(f"watched {eligibility.watched_age_days}d")
        detail = ", ".join(ages) + rating
        return f"- {candidate.display_name}: {eligibility.reason}{' (' + detail.strip(', ') + ')' if detail else ''}"

    def preview(self):
        settings = self._retention_settings()
        policy = RetentionPolicy(settings, self.exclusions)
        eligible = []
        skipped = {}
        total = 0
        for candidate in self.enumerator.iter_candidates(settings):
            total += 1
            result = policy.evaluate(candidate)
            if result.eligible:
                if len(eligible) < self.PREVIEW_LIMIT:
                    eligible.append(self._item_line(candidate, result))
            else:
                skipped[result.reason] = skipped.get(result.reason, 0) + 1
        eligible_count = sum(1 for _ in self._eligible_candidates(settings, policy))
        lines = [
            f"Eligible: {eligible_count}",
            f"Resolved candidates: {total}",
            f"Maximum deletions per run: {settings.max_deletions}",
            f"Background dry run: {'yes' if settings.background_dry_run else 'no'}",
            "",
            "Eligible items:",
        ]
        lines.extend(eligible or ["- None"])
        if eligible_count > len(eligible):
            lines.append(f"- ... and {eligible_count - len(eligible)} more")
        lines.extend(["", "Skipped by policy:"])
        lines.extend([f"- {reason}: {count}" for reason, count in sorted(skipped.items())] or ["- None"])
        for reason, count in sorted(self.enumerator.skipped.items()):
            lines.append(f"- Enumeration {reason}: {count}")
        text = "\n".join(lines)
        self._save_report("preview", True, eligible_count, [], skipped)
        return text

    def _eligible_candidates(self, settings, policy):
        for candidate in self.enumerator.iter_candidates(settings):
            eligibility = policy.evaluate(candidate)
            if eligibility.eligible:
                yield candidate, eligibility

    def run(self, scheduled=False):
        settings = self._retention_settings()
        dry_run = settings.background_dry_run if scheduled else bool(self.settings.dry_run)
        if scheduled:
            if not settings.periodic_enabled:
                return {"status": "disabled"}
            if not dry_run and settings.auth_generation != pin_policy_generation(self.settings):
                self.addon.setSetting("retention_periodic_enabled", "false")
                return {"status": "authorization_stale"}
        elif not dry_run and not authorize_action("retention_run", self.settings, self.ui):
            return {"status": "cancelled"}

        if not self.state.acquire_lock():
            return {"status": "already_running"}
        started = time.time()
        items = []
        processed = 0
        deleted = 0
        failed = 0
        skipped = {}
        progress = None
        try:
            policy = RetentionPolicy(settings, self.exclusions)
            if not scheduled:
                prompt = (
                    f"Process up to {settings.max_deletions} eligible item(s)?\n\n"
                    f"Mode: {'dry run' if dry_run else 'REAL API DELETION'}"
                )
                if not self.ui.confirm("Retention cleanup", prompt):
                    return {"status": "cancelled"}
                progress = self.ui.progress("Retention cleanup", "Evaluating media")

            for candidate in self.enumerator.iter_candidates(settings):
                eligibility = policy.evaluate(candidate)
                if not eligibility.eligible:
                    skipped[eligibility.reason] = skipped.get(eligibility.reason, 0) + 1
                    continue
                if processed >= settings.max_deletions:
                    break
                if progress is not None:
                    if progress.iscanceled():
                        break
                    progress.update(min(99, int(processed * 100 / max(1, settings.max_deletions))), candidate.display_name)
                report_item = self.executor.execute(candidate, policy, dry_run=dry_run)
                items.append(report_item.as_dict())
                processed += 1
                deleted += report_item.action_taken == "deleted"
                failed += report_item.action_taken == "failed"

            next_due = time.time() + settings.interval_hours * 3600 if settings.periodic_enabled else 0
            report = self._save_report(
                "scheduled" if scheduled else "manual", dry_run, processed, items, skipped,
                started=started, next_due=next_due,
            )
            self.state.save_state(
                last_started=self._iso(started), last_completed=self._iso(), next_due=next_due,
                last_status="failed" if failed else "completed",
            )
            if scheduled and settings.notification_mode != "silent":
                if failed or (deleted and settings.notification_mode == "deletions_and_errors"):
                    self.ui.notification(
                        f"Retention: {deleted} deleted, {failed} failed, {processed} processed",
                        error=bool(failed),
                    )
            return report
        finally:
            if progress is not None:
                try:
                    progress.close()
                except Exception:
                    pass
            self.state.release_lock()

    def _save_report(self, run_type, dry_run, candidate_count, items, skipped, started=None, next_due=0):
        report = {
            "run_type": run_type,
            "dry_run": bool(dry_run),
            "started": self._iso(started),
            "completed": self._iso(),
            "candidate_count": int(candidate_count),
            "processed_count": len(items),
            "deleted_count": sum(row.get("action_taken") == "deleted" for row in items),
            "failed_count": sum(row.get("action_taken") == "failed" for row in items),
            "skipped": {str(key)[:200]: int(value) for key, value in skipped.items()},
            "items": items[:100],
            "next_due": self._iso(next_due) if next_due else "",
        }
        self.state.save_report(report)
        return report

    def report_text(self):
        report = self.state.load_report()
        if not report:
            return "No retention report is available."
        lines = [
            f"Run: {report.get('run_type', '?')}",
            f"Dry run: {'yes' if report.get('dry_run') else 'no'}",
            f"Started: {report.get('started', '?')}",
            f"Completed: {report.get('completed', '?')}",
            f"Processed: {report.get('processed_count', 0)}",
            f"Deleted: {report.get('deleted_count', 0)}",
            f"Failed: {report.get('failed_count', 0)}",
        ]
        for item in report.get("items") or []:
            lines.append(f"- {item.get('display_name', '?')}: {item.get('action_taken', '?')} - {item.get('reason', '')}")
        return "\n".join(lines)

    def enable_periodic(self):
        settings = self._retention_settings()
        if not settings.background_dry_run and not authorize_action("retention_run", self.settings, self.ui):
            return False
        generation = pin_policy_generation(self.settings)
        self.addon.setSetting("retention_enabled", "true")
        self.addon.setSetting("retention_periodic_enabled", "true")
        self.addon.setSetting("retention_auth_generation", generation)
        self.state.save_state(next_due=time.time() + settings.interval_hours * 3600, last_status="enabled")
        return True

    def disable_periodic(self):
        self.addon.setSetting("retention_periodic_enabled", "false")
        self.addon.setSetting("retention_auth_generation", "")
        self.state.save_state(next_due=0, last_status="disabled")
        return True

    def add_exclusion(self, selected):
        if selected.media_type == "movie":
            movie = resolve_movie(selected, self.manager.radarr, self.settings.path_mapper)
            tmdb = str(movie.get("tmdbId") or selected.unique_ids.get("tmdb") or "").strip()
            key = f"movie:tmdb:{tmdb}" if tmdb else f"movie:radarr:{as_int(movie.get('id'))}"
            return self.exclusions.add(key, selected.display_name, "movie")
        if selected.media_type not in {"tvshow", "episode"}:
            raise ResolutionError("Retention exclusions support movies, series and seasons")
        series = resolve_series(selected, self.manager.sonarr, self.settings.path_mapper)
        tvdb = as_int(series.get("tvdbId"))
        series_key = f"series:tvdb:{tvdb}" if tvdb > 0 else f"series:sonarr:{as_int(series.get('id'))}"
        if selected.media_type == "tvshow":
            return self.exclusions.add(series_key, selected.display_name, "series")
        choice = self.ui.select(
            "Exclude from automatic retention",
            [f"Entire series: {series.get('title') or selected.tvshow_title}", f"Season {selected.season}"],
        )
        if choice < 0:
            return False
        if choice == 0:
            return self.exclusions.add(series_key, str(series.get("title") or selected.tvshow_title), "series")
        return self.exclusions.add(
            f"{series_key}:season:{selected.season}",
            f"{series.get('title') or selected.tvshow_title} - Season {selected.season}",
            "season",
        )

    def manage_exclusions(self):
        entries = self.exclusions.load()
        if not entries:
            self.ui.ok("Retention exclusions", "No movies, series or seasons are excluded.")
            return False
        labels = [f"{row['scope'].title()}: {row['label']}" for row in entries]
        choice = self.ui.select("Remove a retention exclusion", labels)
        if choice < 0:
            return False
        return self.exclusions.remove(entries[choice]["key"])
