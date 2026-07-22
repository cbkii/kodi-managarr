# SPDX-License-Identifier: GPL-3.0-or-later
import math
import time

from .models import RetentionEligibility

SECONDS_PER_DAY = 86400


def timestamp_state(timestamp, now):
    if timestamp is None:
        return "missing", None
    try:
        value = float(timestamp)
    except (TypeError, ValueError):
        return "invalid", None
    if not math.isfinite(value) or value <= 0:
        return "invalid", None
    if value > now:
        return "future", value
    return "valid", value


def complete_days(now, timestamp):
    state, value = timestamp_state(timestamp, float(now))
    if state != "valid":
        return None
    return int((float(now) - value) // SECONDS_PER_DAY)


class RetentionPolicy:
    def __init__(self, settings, current_time=None):
        self.settings = settings
        self.current_time = float(current_time if current_time is not None else time.time())

    def evaluate(self, candidate):
        passed = []
        failed = []

        if self.settings.watched_only and not candidate.watched:
            return RetentionEligibility(
                False,
                "not_watched",
                failed_rules=("watched_required",),
            )

        added_state, _ = timestamp_state(candidate.date_added, self.current_time)
        watched_state, _ = timestamp_state(candidate.last_played, self.current_time)
        added_age = complete_days(self.current_time, candidate.date_added)
        watched_age = complete_days(self.current_time, candidate.last_played)
        outcomes = []

        if self.settings.use_added_age:
            if added_state == "future":
                outcomes.append(False)
                failed.append("added_date_in_future")
            elif added_state != "valid":
                outcomes.append(False)
                failed.append("added_date_missing_or_invalid")
            elif added_age >= self.settings.added_age_days:
                outcomes.append(True)
                passed.append("added_age")
            else:
                outcomes.append(False)
                failed.append("added_age_too_recent")

        if self.settings.use_watched_age:
            if not candidate.watched:
                outcomes.append(False)
                failed.append("watched_age_requires_watched")
            elif watched_state == "future":
                outcomes.append(False)
                failed.append("watched_date_in_future")
            elif watched_state != "valid":
                outcomes.append(False)
                failed.append("watched_date_missing_or_invalid")
            elif watched_age >= self.settings.watched_age_days:
                outcomes.append(True)
                passed.append("watched_age")
            else:
                outcomes.append(False)
                failed.append("watched_age_too_recent")

        if not outcomes:
            return RetentionEligibility(
                False,
                "no_criteria",
                failed_rules=("no_criteria",),
                added_age_days=added_age,
                watched_age_days=watched_age,
            )

        eligible = all(outcomes) if self.settings.criteria_mode == "all" else any(outcomes)
        reason = "eligible" if eligible else (
            "criteria_not_all_met" if self.settings.criteria_mode == "all" else "criteria_none_met"
        )
        return RetentionEligibility(
            eligible,
            reason,
            passed_rules=tuple(passed),
            failed_rules=tuple(failed),
            added_age_days=added_age,
            watched_age_days=watched_age,
        )
