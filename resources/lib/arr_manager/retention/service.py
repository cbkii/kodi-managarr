# SPDX-License-Identifier: GPL-3.0-or-later
import time

from ..errors import ConfigurationError, SafetyError
from ..messages import message
from .auth import pin_generation
from .config import RetentionSettings
from .enumerator import RetentionEnumerator
from .executor import RetentionExecutor
from .policy import RetentionPolicy
from .reports import RetentionStateStore


class RetentionService:
    def __init__(self, arr_manager, ui, logger):
        self.manager = arr_manager
        self.ui = ui
        self.logger = logger
        self.addon = arr_manager.settings.addon
        self.store = RetentionStateStore(self.addon)

    def _m(self, key, **values):
        return message(self.addon, key, **values)

    def _components(self):
        settings = RetentionSettings(self.addon).validate()
        policy = RetentionPolicy(settings)
        enumerator = RetentionEnumerator(
            self.ui.jsonrpc,
            self.manager,
            self.manager.settings.path_mapper,
            self.logger,
        )
        executor = RetentionExecutor(
            self.manager,
            self.ui.jsonrpc,
            enumerator,
            policy,
            self.logger,
        )
        return settings, policy, enumerator, executor

    @staticmethod
    def _protect_shared_files(evaluated):
        groups = {}
        for index, (candidate, _eligibility) in enumerate(evaluated):
            if candidate.media_type == "episode":
                groups.setdefault((candidate.arr_id, candidate.file_id), []).append(index)
        for indexes in groups.values():
            expected = max(
                max(1, int(evaluated[index][0].linked_episode_count or 1))
                for index in indexes
            )
            incomplete = len(indexes) != expected
            has_protected = any(not evaluated[index][1].eligible for index in indexes)
            if not incomplete and not has_protected:
                continue
            reason = (
                "Shared episode file is missing linked Kodi episodes"
                if incomplete
                else "Shared episode file contains a protected episode"
            )
            rule = "shared_file_incomplete" if incomplete else "shared_file_protected"
            for index in indexes:
                eligibility = evaluated[index][1]
                if eligibility.eligible:
                    eligibility.eligible = False
                    eligibility.reason = reason
                    eligibility.failed_rules.append(rule)
        return evaluated

    def _evaluate(self, settings, policy, enumerator):
        candidates = enumerator.get_candidates(settings)
        evaluated = [(candidate, policy.evaluate(candidate)) for candidate in candidates]
        return self._protect_shared_files(evaluated)

    @staticmethod
    def _eligible_unique(evaluated):
        result = []
        seen = set()
        for candidate, eligibility in evaluated:
            if not eligibility.eligible or not candidate.file_id:
                continue
            key = (
                ("movie", candidate.db_id)
                if candidate.media_type == "movie"
                else ("episode-file", candidate.arr_id, candidate.file_id)
            )
            if key in seen:
                continue
            seen.add(key)
            result.append(candidate)
        return result

    def run_preview(self, _selected=None):
        settings, policy, enumerator, _executor = self._components()
        evaluated = self._evaluate(settings, policy, enumerator)
        eligible = self._eligible_unique(evaluated)
        reasons = {}
        for _candidate, eligibility in evaluated:
            if not eligibility.eligible:
                reasons[eligibility.reason] = reasons.get(eligibility.reason, 0) + 1
        lines = [
            self._m("retention_preview_summary", eligible=len(eligible), limit=settings.max_deletions),
            "",
        ]
        for candidate in eligible[:settings.max_deletions]:
            lines.append(f"- {candidate.display_name}")
        if len(eligible) > settings.max_deletions:
            lines.append(self._m("retention_preview_more", count=len(eligible) - settings.max_deletions))
        if reasons:
            lines.extend(["", self._m("retention_skipped_heading")])
            for reason, count in sorted(reasons.items(), key=lambda item: (-item[1], item[0])):
                lines.append(f"- {count}: {reason}")
        text = "\n".join(lines)
        self.ui.text(self._m("retention_preview_heading"), text)
        return text

    def run_cleanup_now(self, _selected=None):
        settings, policy, enumerator, executor = self._components()
        evaluated = self._evaluate(settings, policy, enumerator)
        eligible = self._eligible_unique(evaluated)
        if not eligible:
            self.ui.ok(self._m("retention_cleanup_heading"), self._m("retention_none_eligible"))
            return "no_eligible"
        count = min(len(eligible), settings.max_deletions)
        if not self.ui.confirm(
            self._m("retention_cleanup_heading"),
            self._m("retention_cleanup_confirm", count=count, dry_run=str(settings.manual_dry_run)),
        ):
            return "cancelled"
        if not self.store.acquire_lock():
            raise SafetyError(self._m("retention_locked"))
        try:
            summary = self._run_pass(
                eligible[:settings.max_deletions],
                executor,
                settings.manual_dry_run,
                interactive=True,
            )
            summary["skipped"] += max(0, len(eligible) - settings.max_deletions)
            self._save_report("manual", settings.manual_dry_run, summary)
        finally:
            self.store.release_lock()
        self.ui.ok(self._m("retention_cleanup_complete"), self._summary_text(summary))
        return summary

    def enable_periodic(self, _selected=None):
        settings = RetentionSettings(self.addon).validate()
        next_due = time.time() + settings.interval_hours * 3600
        self.store.save_state(pin_generation(self.manager.settings), next_due)
        self.addon.setSetting("retention_periodic_enabled", "true")
        self.ui.notification(self._m("retention_periodic_enabled", hours=settings.interval_hours))
        return "enabled"

    def disable_periodic(self, _selected=None):
        self.addon.setSetting("retention_periodic_enabled", "false")
        self.store.save_state("", 0)
        self.ui.notification(self._m("retention_periodic_disabled"))
        return "disabled"

    def view_report(self, _selected=None):
        report = self.store.load_report()
        if not report:
            self.ui.ok(self._m("retention_report_heading"), self._m("retention_no_report"))
            return ""
        lines = [
            self._m("retention_report_type", run_type=report.get("run_type", "unknown")),
            self._m("retention_report_dry_run", dry_run=str(bool(report.get("dry_run")))),
            self._m(
                "retention_report_counts",
                deleted=report.get("deleted", 0),
                planned=report.get("planned", 0),
                failed=report.get("failed", 0),
                skipped=report.get("skipped", 0),
            ),
        ]
        for item in report.get("results", []):
            line = f"- {item.get('name', '')}: {item.get('action', '')}"
            if item.get("error"):
                line += f" ({item['error']})"
            lines.append(line)
        text = "\n".join(lines)
        self.ui.text(self._m("retention_report_heading"), text)
        return text

    def run_background(self):
        try:
            settings = RetentionSettings(self.addon)
            if not settings.enabled or not settings.periodic_enabled:
                return None
            settings.validate()
        except ConfigurationError as exc:
            if self.logger:
                self.logger.error("Periodic retention configuration is invalid: %s", exc)
            return None
        state = self.store.load_state()
        now = time.time()
        if now < float(state.get("next_due") or 0):
            return None
        current_generation = pin_generation(self.manager.settings)
        if not settings.background_dry_run and state.get("auth_generation") != current_generation:
            self.addon.setSetting("retention_periodic_enabled", "false")
            if self.logger:
                self.logger.error("Periodic retention disabled because PIN authorisation changed")
            self.ui.notification(self._m("retention_periodic_auth_changed"), error=True)
            return None
        if not self.store.acquire_lock():
            return None
        try:
            settings, policy, enumerator, executor = self._components()
            evaluated = self._evaluate(settings, policy, enumerator)
            all_eligible = self._eligible_unique(evaluated)
            eligible = all_eligible[:settings.max_deletions]
            summary = self._run_pass(eligible, executor, settings.background_dry_run, interactive=False)
            summary["skipped"] += max(0, len(all_eligible) - len(eligible))
            self._save_report("periodic", settings.background_dry_run, summary)
            self.store.save_state(current_generation, time.time() + settings.interval_hours * 3600)
            self._notify_background(settings, summary)
            return summary
        except Exception:
            if self.logger:
                self.logger.exception("Periodic retention run failed before completion")
            self.store.save_state(current_generation, time.time() + 3600)
            return None
        finally:
            self.store.release_lock()

    def _run_pass(self, candidates, executor, dry_run, interactive):
        results = []
        progress = (
            self.ui.progress(self._m("retention_cleanup_heading"), self._m("retention_progress"))
            if interactive
            else None
        )
        try:
            for index, candidate in enumerate(candidates):
                if self._abort_requested(progress):
                    break
                if progress is not None:
                    progress.update(
                        int((index + 1) / max(len(candidates), 1) * 100),
                        self._m("retention_processing", name=candidate.display_name),
                    )
                results.append(executor.execute(candidate, dry_run=dry_run))
        finally:
            if progress is not None:
                progress.close()
        return {
            "deleted": sum(item.action_taken == "deleted" for item in results),
            "planned": sum(item.action_taken == "dry_run" for item in results),
            "failed": sum(item.action_taken == "failed" for item in results),
            "skipped": max(0, len(candidates) - len(results)),
            "results": results,
        }

    def _abort_requested(self, progress):
        if progress is not None and getattr(progress, "iscanceled", lambda: False)():
            return True
        monitor = getattr(self.ui, "monitor", None)
        return bool(monitor and getattr(monitor, "abortRequested", lambda: False)())

    def _save_report(self, run_type, dry_run, summary):
        self.store.save_report({
            "run_type": run_type,
            "dry_run": bool(dry_run),
            "timestamp": time.time(),
            "deleted": summary["deleted"],
            "planned": summary["planned"],
            "failed": summary["failed"],
            "skipped": summary["skipped"],
            "results": [
                {
                    "name": item.display_name,
                    "action": item.action_taken,
                    "reason": item.reason,
                    "error": item.error_message,
                }
                for item in summary["results"]
            ],
        })

    def _summary_text(self, summary):
        return self._m(
            "retention_summary",
            deleted=summary["deleted"],
            planned=summary["planned"],
            failed=summary["failed"],
            skipped=summary["skipped"],
        )

    def _notify_background(self, settings, summary):
        if settings.notification_mode == "silent":
            return
        if settings.notification_mode == "errors_only" and not summary["failed"]:
            return
        if settings.notification_mode == "deletions_and_errors" and not (summary["deleted"] or summary["failed"]):
            return
        self.ui.notification(self._summary_text(summary), error=bool(summary["failed"]))
