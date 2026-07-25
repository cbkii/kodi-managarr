# SPDX-License-Identifier: GPL-3.0-or-later
import time

from .models import RetentionEligibility

_SECONDS_PER_DAY = 86400


class RetentionPolicy:
    def __init__(self, settings, current_time=None):
        self.settings = settings
        self.current_time = float(current_time if current_time is not None else time.time())

    def _exclusion_reason(self, candidate):
        exclusions = self.settings.exclusions
        if candidate.media_type == "movie" and candidate.db_id in exclusions["movie"]:
            return "Explicit movie exclusion"
        if candidate.media_type == "episode":
            if candidate.db_id in exclusions["episode"]:
                return "Explicit episode exclusion"
            if candidate.tvshow_db_id in exclusions["series"]:
                return "Explicit series exclusion"
            if (candidate.tvshow_db_id, int(candidate.season or 0)) in exclusions["season"]:
                return "Explicit season exclusion"
        return ""

    def evaluate(self, candidate):
        exclusion = self._exclusion_reason(candidate)
        if exclusion:
            return RetentionEligibility(False, exclusion, failed_rules=["excluded"])

        threshold = self.settings.movie_rating_threshold
        if candidate.media_type == "movie" and threshold > 0:
            rating = candidate.rating
            if rating is None or rating <= 0:
                return RetentionEligibility(
                    False,
                    "Movie rating unavailable while rating protection is enabled",
                    failed_rules=["rating_unknown"],
                )
            if rating >= threshold:
                return RetentionEligibility(
                    False,
                    f"Movie rating protected ({rating:.1f} >= {threshold:.1f})",
                    failed_rules=["rating_protected"],
                )

        passed = []
        failed = []
        if self.settings.watched_only and not candidate.watched:
            return RetentionEligibility(False, "Not watched", failed_rules=["watched"])

        results = []
        if self.settings.use_added_age:
            ok, detail = self._age_rule(candidate.date_added, self.settings.added_age_days, "added")
            results.append(ok)
            (passed if ok else failed).append(detail)
        if self.settings.use_watched_age:
            if not candidate.watched:
                ok, detail = False, "watched_age_not_watched"
            else:
                ok, detail = self._age_rule(candidate.last_played, self.settings.watched_age_days, "watched")
            results.append(ok)
            (passed if ok else failed).append(detail)

        eligible = all(results) if self.settings.criteria_mode == "all" else any(results)
        if eligible:
            return RetentionEligibility(True, "Criteria met", passed_rules=passed, failed_rules=failed)
        reason = "Failed all required criteria" if self.settings.criteria_mode == "all" else "Failed to meet any criterion"
        return RetentionEligibility(False, reason, passed_rules=passed, failed_rules=failed)

    def _age_rule(self, timestamp, minimum_days, name):
        if timestamp is None:
            return False, f"{name}_age_missing_date"
        if timestamp > self.current_time:
            return False, f"{name}_age_future_date"
        age_days = int((self.current_time - timestamp) / _SECONDS_PER_DAY)
        if age_days >= minimum_days:
            return True, f"{name}_age_passed ({age_days} >= {minimum_days})"
        return False, f"{name}_age_failed ({age_days} < {minimum_days})"
