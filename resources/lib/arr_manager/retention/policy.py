# SPDX-License-Identifier: GPL-3.0-or-later
import math
import time

from .models import RetentionEligibility

SECONDS_PER_DAY = 86400


class RetentionPolicy:
    def __init__(self, settings, exclusions, current_time=None):
        self.settings = settings
        self.exclusions = exclusions
        self.current_time = float(current_time if current_time is not None else time.time())

    def _age(self, timestamp, name):
        if timestamp is None:
            return None, f"{name}_missing"
        try:
            value = float(timestamp)
        except (TypeError, ValueError):
            return None, f"{name}_invalid"
        if not math.isfinite(value) or value <= 0:
            return None, f"{name}_invalid"
        if value > self.current_time:
            return None, f"{name}_future"
        return int((self.current_time - value) // SECONDS_PER_DAY), ""

    def evaluate(self, candidate):
        exclusion = self.exclusions.is_excluded(candidate)
        if exclusion:
            return RetentionEligibility(False, f"Excluded from retention: {exclusion['label']}", failed_rules=["excluded"])

        if candidate.media_type == "movie" and self.settings.rating_protection:
            if candidate.rating is not None and candidate.rating >= self.settings.rating_threshold:
                return RetentionEligibility(
                    False,
                    f"Protected by movie rating {candidate.rating:.1f} >= {self.settings.rating_threshold:.1f}",
                    failed_rules=["rating_protected"],
                )

        if self.settings.watched_only and not candidate.watched:
            return RetentionEligibility(False, "Not watched", failed_rules=["watched_required"])

        passed = []
        failed = []
        outcomes = []
        added_days = None
        watched_days = None

        if self.settings.use_added_age:
            added_days, error = self._age(candidate.date_added, "added_age")
            ok = not error and added_days >= self.settings.added_age_days
            outcomes.append(ok)
            if ok:
                passed.append(f"added_age:{added_days}")
            else:
                failed.append(error or f"added_age:{added_days}<{self.settings.added_age_days}")

        if self.settings.use_watched_age:
            if not candidate.watched:
                watched_days, error = None, "watched_age_not_watched"
            else:
                watched_days, error = self._age(candidate.last_played, "watched_age")
            ok = not error and watched_days >= self.settings.watched_age_days
            outcomes.append(ok)
            if ok:
                passed.append(f"watched_age:{watched_days}")
            else:
                failed.append(error or f"watched_age:{watched_days}<{self.settings.watched_age_days}")

        if not outcomes:
            return RetentionEligibility(False, "No enabled age criteria", failed_rules=["no_criteria"])
        eligible = all(outcomes) if self.settings.criteria_mode == "all" else any(outcomes)
        reason = "Criteria met" if eligible else (
            "Failed one or more required criteria" if self.settings.criteria_mode == "all" else "Failed every enabled criterion"
        )
        return RetentionEligibility(
            eligible,
            reason,
            passed_rules=passed,
            failed_rules=failed,
            added_age_days=added_days,
            watched_age_days=watched_days,
        )
