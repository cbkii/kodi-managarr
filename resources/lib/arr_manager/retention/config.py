# SPDX-License-Identifier: GPL-3.0-or-later
import re

from ..errors import ConfigurationError
from ..util import as_bool, as_int

_EXCLUSION_RE = re.compile(r"^(movie|episode|series):(\d+)$|^season:(\d+):(\d+)$", re.I)


def _as_float(value, default=0.0, minimum=0.0, maximum=10.0):
    try:
        result = float(str(value or "").strip())
    except (TypeError, ValueError):
        result = float(default)
    return min(max(result, minimum), maximum)


def parse_exclusions(raw):
    result = {"movie": set(), "episode": set(), "series": set(), "season": set()}
    text = str(raw or "").replace("\r", "\n")
    for token in re.split(r"[;,\n]+", text):
        token = token.strip().lower()
        if not token:
            continue
        match = _EXCLUSION_RE.fullmatch(token)
        if not match:
            raise ConfigurationError(
                "Invalid retention exclusion. Use movie:<Kodi ID>, episode:<Kodi ID>, "
                "series:<Kodi TV show ID>, or season:<Kodi TV show ID>:<season>."
            )
        kind = match.group(1)
        if kind:
            value = int(match.group(2))
            if value <= 0:
                raise ConfigurationError("Retention exclusion IDs must be positive integers.")
            result[kind].add(value)
            continue
        show_id = int(match.group(3))
        season = int(match.group(4))
        if show_id <= 0 or season < 0:
            raise ConfigurationError("Retention season exclusions require a positive show ID and non-negative season.")
        result["season"].add((show_id, season))
    return result


class RetentionSettings:
    def __init__(self, addon):
        self.addon = addon
        get = addon.getSetting
        self.enabled = as_bool(get("retention_enabled"), False)
        self.include_movies = as_bool(get("retention_include_movies"), False)
        self.include_episodes = as_bool(get("retention_include_episodes"), False)
        self.watched_only = as_bool(get("retention_watched_only"), True)
        self.use_added_age = as_bool(get("retention_use_added_age"), True)
        self.added_age_days = as_int(get("retention_added_age_days"), 30, 0, 9999)
        self.use_watched_age = as_bool(get("retention_use_watched_age"), True)
        self.watched_age_days = as_int(get("retention_watched_age_days"), 30, 0, 9999)
        self.criteria_mode = (get("retention_criteria_mode") or "all").strip().lower()
        if self.criteria_mode not in {"all", "any"}:
            self.criteria_mode = "all"
        self.movie_rating_threshold = _as_float(get("retention_movie_rating_threshold"), 0.0)
        self.exclusions = parse_exclusions(get("retention_exclusions"))
        self.manual_dry_run = as_bool(get("retention_manual_dry_run"), True)
        self.periodic_enabled = as_bool(get("retention_periodic_enabled"), False)
        self.interval_hours = as_int(get("retention_interval_hours"), 24, 1, 720)
        self.max_deletions = as_int(get("retention_max_deletions"), 5, 1, 100)
        self.background_dry_run = as_bool(get("retention_background_dry_run"), True)
        self.notification_mode = (get("retention_notification_mode") or "errors_only").strip().lower()
        if self.notification_mode not in {"errors_only", "deletions_and_errors", "silent"}:
            self.notification_mode = "errors_only"

    def validate(self):
        if not self.enabled:
            raise ConfigurationError("Retention is disabled in add-on settings.")
        if not self.include_movies and not self.include_episodes:
            raise ConfigurationError("Retention requires movies and/or episodes to be included.")
        if not self.use_added_age and not self.use_watched_age:
            raise ConfigurationError("Retention requires at least one age criterion.")
        return self
