# SPDX-License-Identifier: GPL-3.0-or-later
import time
from .models import RetentionCandidate, RetentionEligibility

class RetentionPolicy:
    def __init__(self, settings, current_time=None):
        self.settings = settings
        # Used for testing/stable execution
        self.current_time = current_time if current_time is not None else time.time()
        self.SECONDS_PER_DAY = 86400

    def evaluate(self, candidate: RetentionCandidate) -> RetentionEligibility:
        """
        Evaluate if a candidate is eligible for retention (deletion).
        """
        passed = []
        failed = []

        # 1. Check watched requirement (mandatory gate if enabled)
        if self.settings.watched_only and not candidate.watched:
            return RetentionEligibility(False, "Not watched", passed_rules=passed, failed_rules=["watched"])

        has_rules = False

        # 2. Check Added Age
        added_ok = None
        if self.settings.use_added_age:
            has_rules = True
            if candidate.date_added is None:
                added_ok = False
                failed.append("added_age_missing_date")
            elif candidate.date_added > self.current_time:
                added_ok = False
                failed.append("added_age_future_date")
            else:
                age_seconds = self.current_time - candidate.date_added
                age_days = int(age_seconds / self.SECONDS_PER_DAY)
                if age_days >= self.settings.added_age_days:
                    added_ok = True
                    passed.append(f"added_age_passed ({age_days} >= {self.settings.added_age_days})")
                else:
                    added_ok = False
                    failed.append(f"added_age_failed ({age_days} < {self.settings.added_age_days})")

        # 3. Check Watched Age
        watched_ok = None
        if self.settings.use_watched_age:
            has_rules = True
            if not candidate.watched:
                 watched_ok = False
                 failed.append("watched_age_not_watched")
            elif candidate.last_played is None:
                watched_ok = False
                failed.append("watched_age_missing_date")
            elif candidate.last_played > self.current_time:
                watched_ok = False
                failed.append("watched_age_future_date")
            else:
                age_seconds = self.current_time - candidate.last_played
                age_days = int(age_seconds / self.SECONDS_PER_DAY)
                if age_days >= self.settings.watched_age_days:
                    watched_ok = True
                    passed.append(f"watched_age_passed ({age_days} >= {self.settings.watched_age_days})")
                else:
                    watched_ok = False
                    failed.append(f"watched_age_failed ({age_days} < {self.settings.watched_age_days})")

        if not has_rules:
            # Reject configuration with no meaningful criteria instead of making entire library eligible
            return RetentionEligibility(False, "No enabled criteria", passed_rules=[], failed_rules=["no_criteria"])

        # 4. AND/OR Evaluation
        is_all = self.settings.criteria_mode == "all"

        eligible = False
        if is_all:
            # All ENABLED rules must pass
            eligible = True
            if self.settings.use_added_age and not added_ok:
                eligible = False
            if self.settings.use_watched_age and not watched_ok:
                eligible = False
        else:
            # ANY ENABLED rule must pass
            if self.settings.use_added_age and added_ok:
                eligible = True
            if self.settings.use_watched_age and watched_ok:
                eligible = True

        if eligible:
            return RetentionEligibility(True, "Criteria met", passed_rules=passed, failed_rules=failed)
        else:
            reason = "Failed all required criteria" if is_all else "Failed to meet any criteria"
            return RetentionEligibility(False, reason, passed_rules=passed, failed_rules=failed)
