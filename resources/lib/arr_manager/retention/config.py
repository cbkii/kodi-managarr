# SPDX-License-Identifier: GPL-3.0-or-later
from dataclasses import dataclass

from ..errors import ConfigurationError
from ..util import as_bool, as_int


@dataclass(frozen=True)
class RetentionSettings:
    enabled: bool
    include_movies: bool
    include_episodes: bool
    watched_only: bool
    use_added_age: bool
    added_age_days: int
    use_watched_age: bool
    watched_age_days: int
    criteria_mode: str
    rating_protection: bool
    rating_threshold: float
    periodic_enabled: bool
    interval_hours: int
    max_deletions: int
    background_dry_run: bool
    notification_mode: str
    auth_generation: str

    @classmethod
    def from_addon(cls, addon):
        get = addon.getSetting
        raw_rating = (get("retention_rating_threshold") or "7.0").strip()
        try:
            rating = float(raw_rating)
        except (TypeError, ValueError) as exc:
            raise ConfigurationError("Retention movie rating threshold must be a number from 0.0 to 10.0") from exc
        if not 0.0 <= rating <= 10.0:
            raise ConfigurationError("Retention movie rating threshold must be from 0.0 to 10.0")
        mode = (get("retention_criteria_mode") or "all").strip().lower()
        if mode not in {"all", "any"}:
            raise ConfigurationError("Retention criteria mode must be all or any")
        notify = (get("retention_notification_mode") or "errors_only").strip().lower()
        if notify not in {"errors_only", "deletions_and_errors", "silent"}:
            raise ConfigurationError("Retention notification mode is invalid")
        return cls(
            enabled=as_bool(get("retention_enabled"), False),
            include_movies=as_bool(get("retention_include_movies"), True),
            include_episodes=as_bool(get("retention_include_episodes"), True),
            watched_only=as_bool(get("retention_watched_only"), True),
            use_added_age=as_bool(get("retention_use_added_age"), True),
            added_age_days=as_int(get("retention_added_age_days"), 30, 0, 9999),
            use_watched_age=as_bool(get("retention_use_watched_age"), True),
            watched_age_days=as_int(get("retention_watched_age_days"), 30, 0, 9999),
            criteria_mode=mode,
            rating_protection=as_bool(get("retention_rating_protection"), False),
            rating_threshold=rating,
            periodic_enabled=as_bool(get("retention_periodic_enabled"), False),
            interval_hours=as_int(get("retention_interval_hours"), 24, 1, 720),
            max_deletions=as_int(get("retention_max_deletions"), 5, 1, 100),
            background_dry_run=as_bool(get("retention_background_dry_run"), True),
            notification_mode=notify,
            auth_generation=(get("retention_auth_generation") or "").strip(),
        )

    def validate(self, require_enabled=True):
        if require_enabled and not self.enabled:
            raise ConfigurationError("Retention is disabled")
        if not self.include_movies and not self.include_episodes:
            raise ConfigurationError("Retention must include movies, episodes, or both")
        if not self.use_added_age and not self.use_watched_age:
            raise ConfigurationError("Retention requires at least one age criterion")
