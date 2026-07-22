# SPDX-License-Identifier: GPL-3.0-or-later
from ..errors import ConfigurationError
from ..util import as_bool


NOTIFICATION_MODES = {"errors_only", "deletions_and_errors", "silent"}
CRITERIA_MODES = {"all", "any"}


def _read_int(raw, default, minimum, maximum, label, errors):
    text = str(raw or "").strip()
    if not text:
        return default
    try:
        value = int(text)
    except (TypeError, ValueError):
        errors.append(f"{label} must be an integer")
        return default
    if value < minimum or value > maximum:
        errors.append(f"{label} must be between {minimum} and {maximum}")
        return default
    return value


class RetentionSettings:
    def __init__(self, addon):
        self.addon = addon
        self.errors = []
        get = addon.getSetting
        self.enabled = as_bool(get("retention_enabled"), False)
        self.include_movies = as_bool(get("retention_include_movies"), True)
        self.include_episodes = as_bool(get("retention_include_episodes"), True)
        self.watched_only = as_bool(get("retention_watched_only"), True)
        self.use_added_age = as_bool(get("retention_use_added_age"), True)
        self.added_age_days = _read_int(
            get("retention_added_age_days"), 30, 0, 9999, "Days since added", self.errors
        )
        self.use_watched_age = as_bool(get("retention_use_watched_age"), True)
        self.watched_age_days = _read_int(
            get("retention_watched_age_days"), 7, 0, 9999, "Days since watched", self.errors
        )
        self.criteria_mode = (get("retention_criteria_mode") or "all").strip().lower()
        if self.criteria_mode not in CRITERIA_MODES:
            self.errors.append("Retention criteria mode must be all or any")
            self.criteria_mode = "all"
        self.periodic_enabled = as_bool(get("retention_periodic_enabled"), False)
        self.interval_hours = _read_int(
            get("retention_interval_hours"), 24, 1, 720, "Retention interval", self.errors
        )
        self.max_deletions = _read_int(
            get("retention_max_deletions"), 5, 1, 100, "Maximum deletions per run", self.errors
        )
        self.background_dry_run = as_bool(get("retention_background_dry_run"), True)
        self.notification_mode = (
            get("retention_notification_mode") or "errors_only"
        ).strip().lower()
        if self.notification_mode not in NOTIFICATION_MODES:
            self.errors.append("Unknown retention notification mode")
            self.notification_mode = "errors_only"

    def validate(self):
        if not self.enabled:
            raise ConfigurationError("Retention is disabled")
        if self.errors:
            raise ConfigurationError(self.errors[0])
        if not self.include_movies and not self.include_episodes:
            raise ConfigurationError("Retention requires movies or episodes to be enabled")
        if not self.use_added_age and not self.use_watched_age:
            raise ConfigurationError("Retention requires at least one age criterion")
        return self
