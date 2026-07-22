# SPDX-License-Identifier: GPL-3.0-or-later
import time
from .config import RetentionSettings
from .enumerator import RetentionEnumerator
from .policy import RetentionPolicy
from .executor import RetentionExecutor
from .reports import RetentionStateStore

class RetentionService:
    def __init__(self, arr_manager, kodi_client, kodi_ui, logger, authoriser=None):
        self.manager = arr_manager
        self.kodi = kodi_client
        self.ui = kodi_ui
        self.logger = logger
        self.authoriser = authoriser

        self.settings = None
        self.policy = None
        self.enumerator = None
        self.executor = None
        self.store = RetentionStateStore(self.manager.settings.addon)

    def _init_components(self):
        self.settings = RetentionSettings(self.manager.settings.addon)
        self.policy = RetentionPolicy(self.settings)
        self.enumerator = RetentionEnumerator(self.kodi, self.manager, self.manager.settings.path_mapper, self.logger)
        self.executor = RetentionExecutor(self.manager, self.kodi, self.ui, self.enumerator, self.logger)

    def _run_pass(self, candidates, dry_run, interactive=False):
        results = []
        skipped = 0
        deleted = 0
        failed = 0

        if interactive:
            progress = self.ui.progress("Retention Cleanup", "Evaluating candidates...")
            if not progress:
                 interactive = False

        try:
            for idx, cand in enumerate(candidates):
                if interactive and self.ui._progress_cancelled(progress):
                    break

                if interactive:
                    self.ui._update_progress(progress, int((idx / len(candidates)) * 100), f"Processing {cand.display_name}")

                eligibility = self.policy.evaluate(cand)
                if not eligibility.eligible:
                    skipped += 1
                    continue

                if deleted >= self.settings.max_deletions:
                    skipped += 1
                    continue # Skip remaining if max hit

                report_item = self.executor.execute_deletion(cand, dry_run=dry_run)
                results.append(report_item)

                if report_item.action_taken == "deleted":
                    deleted += 1
                elif report_item.action_taken == "failed":
                    failed += 1

        finally:
            if interactive:
                self.ui._close_progress(progress)

        return results, skipped, deleted, failed

    def run_preview(self):
        # Re-initialize ensures settings are fresh but for tests we may have patched them
        if not getattr(self, '_test_mode', False):
            self._init_components()
        self.settings.validate()

        candidates = self.enumerator.get_movies(self.settings) + self.enumerator.get_episodes(self.settings)

        eligible_items = []
        skipped_reasons = {}

        for cand in candidates:
            eligibility = self.policy.evaluate(cand)
            if eligibility.eligible:
                eligible_items.append((cand.display_name, eligibility.reason))
            else:
                skipped_reasons[eligibility.reason] = skipped_reasons.get(eligibility.reason, 0) + 1

        # Format preview output
        lines = []
        lines.append(f"Found {len(eligible_items)} eligible items (Batch limit: {self.settings.max_deletions})")
        lines.append("")

        for name, reason in eligible_items[:self.settings.max_deletions]:
            lines.append(f"- {name}")

        if len(eligible_items) > self.settings.max_deletions:
            lines.append(f"... and {len(eligible_items) - self.settings.max_deletions} more")

        lines.append("\nSkipped items summary:")
        for reason, count in skipped_reasons.items():
            lines.append(f"- {count}: {reason}")

        if self.ui:
            self.ui.text("Retention Preview", "\n".join(lines))

        return lines

    def run_cleanup_now(self):
        # Re-initialize ensures settings are fresh but for tests we may have patched them
        if not getattr(self, '_test_mode', False):
            self._init_components()
        self.settings.validate()

        if self.authoriser and not self.authoriser.authorize("Manual Cleanup"):
            if self.ui:
                 self.ui.notification("Cleanup cancelled")
            return "cancelled"

        candidates = self.enumerator.get_movies(self.settings) + self.enumerator.get_episodes(self.settings)

        eligible_count = sum(1 for c in candidates if self.policy.evaluate(c).eligible)
        if eligible_count == 0:
            if self.ui:
                 self.ui.ok("Retention Cleanup", "No eligible items found.")
            return "no_eligible"

        prompt = f"Run cleanup for up to {min(eligible_count, self.settings.max_deletions)} items?"
        if not self.ui.confirm("Retention Cleanup", prompt):
             return "cancelled"

        results, skipped, deleted, failed = self._run_pass(candidates, dry_run=self.settings.background_dry_run, interactive=True)

        summary = f"Deleted: {deleted}\nFailed: {failed}\nSkipped: {skipped}"
        if self.ui:
             self.ui.ok("Retention Cleanup Complete", summary)

        self._save_report("manual", deleted, failed, skipped, results)
        return summary

    def run_background(self):
        if not self.settings.enabled or not self.settings.periodic_enabled:
            return

        try:
             # Re-initialize ensures settings are fresh but for tests we may have patched them
             if not getattr(self, '_test_mode', False):
                 self._init_components()
             self.settings.validate()
        except Exception as e:
             if self.logger:
                 self.logger.error("Retention disabled due to invalid config: %s", e)
             return

        state = self.store.load_state()
        auth_gen = state.get("auth_generation", "")
        if self.authoriser:
            expected_gen = self.authoriser.get_generation()
            if auth_gen != expected_gen:
                if self.logger:
                    self.logger.error("PIN policy changed, background retention requires re-authorization")
                return

        next_due = state.get("next_due", 0)
        if time.time() < next_due:
            return

        if not self.store.acquire_lock():
            return

        try:
            candidates = self.enumerator.get_movies(self.settings) + self.enumerator.get_episodes(self.settings)
            results, skipped, deleted, failed = self._run_pass(candidates, dry_run=self.settings.background_dry_run, interactive=False)

            self._save_report("periodic", deleted, failed, skipped, results)

            if self.settings.notification_mode == "deletions_and_errors" and (deleted > 0 or failed > 0):
                if self.ui:
                    self.ui.notification(f"Retention: {deleted} deleted, {failed} failed")
            elif self.settings.notification_mode == "errors_only" and failed > 0:
                if self.ui:
                    self.ui.notification(f"Retention: {failed} failed deletions", error=True)

            new_next_due = time.time() + (self.settings.interval_hours * 3600)
            self.store.save_state(auth_gen, new_next_due)
        finally:
            self.store.release_lock()

    def _save_report(self, run_type, deleted, failed, skipped, results):
        report = {
            "run_type": run_type,
            "dry_run": self.settings.background_dry_run,
            "timestamp": time.time(),
            "deleted": deleted,
            "failed": failed,
            "skipped_after_eligibility": skipped,
            "results": [
                {
                    "name": r.display_name,
                    "action": r.action_taken,
                    "reason": r.reason,
                    "error": r.error_message
                } for r in results
            ]
        }
        self.store.save_report(report)

    def view_report(self):
        report = self.store.load_report()
        if not report:
            if self.ui:
                self.ui.ok("Retention Report", "No report available.")
            return

        lines = [
            f"Run Type: {report.get('run_type')}",
            f"Dry Run: {report.get('dry_run')}",
            f"Deleted: {report.get('deleted')} | Failed: {report.get('failed')}",
            "\nActions:"
        ]

        for r in report.get("results", []):
            line = f"- {r.get('name')}: {r.get('action')}"
            if r.get('error'):
                line += f" ({r.get('error')})"
            lines.append(line)

        if self.ui:
            self.ui.text("Last Retention Report", "\n".join(lines))

    def enable_periodic(self):
        if self.authoriser and not self.authoriser.authorize("Enable Periodic Retention"):
             if self.ui:
                 self.ui.notification("Enable cancelled")
             return

        gen = self.authoriser.get_generation() if self.authoriser else ""
        next_due = time.time() + (self.settings.interval_hours * 3600)
        self.store.save_state(gen, next_due)

        if self.ui:
            self.manager.settings.addon.setSetting("retention_periodic_enabled", "true")
            self.ui.notification("Periodic retention enabled")

    def disable_periodic(self):
        # Disabling automation never requires a PIN
        self.store.save_state("", 0)
        if self.ui:
             self.manager.settings.addon.setSetting("retention_periodic_enabled", "false")
             self.ui.notification("Periodic retention disabled")
