# SPDX-License-Identifier: GPL-3.0-or-later
from ..util import as_bool, as_int
from ..errors import ConfigurationError

class RetentionSettings:
    def __init__(self, addon):
        get = addon.getSetting

        self.enabled = as_bool(get("retention_enabled"), False)

        self.include_movies = as_bool(get("retention_include_movies"), False)
        self.include_episodes = as_bool(get("retention_include_episodes"), False)

        self.watched_only = as_bool(get("retention_watched_only"), True)

        self.use_added_age = as_bool(get("retention_use_added_age"), True)
        self.added_age_days = as_int(get("retention_added_age_days"), 0, 0, 9999)

        self.use_watched_age = as_bool(get("retention_use_watched_age"), True)
        self.watched_age_days = as_int(get("retention_watched_age_days"), 0, 0, 9999)

        self.criteria_mode = get("retention_criteria_mode") or "all"
        if self.criteria_mode not in {"all", "any"}:
            self.criteria_mode = "all"

        self.periodic_enabled = as_bool(get("retention_periodic_enabled"), False)
        self.interval_hours = as_int(get("retention_interval_hours"), 24, 1, 720)
        self.max_deletions = as_int(get("retention_max_deletions"), 5, 1, 100)
        self.background_dry_run = as_bool(get("retention_background_dry_run"), True)

        self.notification_mode = get("retention_notification_mode") or "errors_only"
        if self.notification_mode not in {"errors_only", "deletions_and_errors", "silent"}:
             self.notification_mode = "errors_only"

    def validate(self):
        if not self.enabled:
             raise ConfigurationError("Retention is disabled.")
        if not self.include_movies and not self.include_episodes:
             raise ConfigurationError("Retention requires at least movies or episodes to be included.")
