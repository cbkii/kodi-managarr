# SPDX-License-Identifier: GPL-3.0-or-later
import math
import re

from ..errors import ConfigurationError

_EXCLUSION_RE = re.compile(r"^(movie|episode|series):(\d+)$|^season:(\d+):(\d+)$", re.I)
_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}


def _strict_bool(value, default, setting_name):
    if value is None or str(value).strip() == "":
        return bool(default)
    normalised = str(value).strip().lower()
    if normalised in _TRUE_VALUES:
        return True
    if normalised in _FALSE_VALUES:
        return False
    raise ConfigurationError(f"Invalid boolean value for retention setting '{setting_name}'.")


def _strict_int(value, default, minimum, maximum, setting_name):
    if value is None or str(value).strip() == "":
        return int(default)
    text = str(value).strip()
    try:
        result = int(text)
    except (TypeError, ValueError) as exc:
        raise ConfigurationError(f"Invalid integer value for retention setting '{setting_name}'.") from exc
    if result < minimum or result > maximum:
        raise ConfigurationError(
            f"Retention setting '{setting_name}' must be between {minimum} and {maximum}."
        )
    return result


def _strict_float(value, default, minimum, maximum, setting_name):
    if value is None or str(value).strip() == "":
        return float(default)
    try:
        result = float(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ConfigurationError(f"Invalid number for retention setting '{setting_name}'.") from exc
    if not math.isfinite(result) or result < minimum or result > maximum:
        raise ConfigurationError(
            f"Retention setting '{setting_name}' must be a finite number between {minimum} and {maximum}."
        )
    return result


def _strict_choice(value, default, choices, setting_name):
    normalised = str(value or default).strip().lower()
    if normalised not in choices:
        raise ConfigurationError(f"Invalid value for retention setting '{setting_name}'.")
    return normalised


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
            item_id = int(match.group(2))
            if item_id <= 0:
                raise ConfigurationError("Retention exclusion IDs must be positive integers.")
            result[kind].add(item_id)
            continue
        show_id = int(match.group(3))
        season = int(match.group(4))
        if show_id <= 0 or season < 0:
            raise ConfigurationError(
                "Retention season exclusions require a positive show ID and non-negative season."
            )
        result["season"].add((show_id, season))
    return result


class RetentionSettings:
    def __init__(self, addon):
        self.addon = addon
        get = addon.getSetting
        self.enabled = _strict_bool(get("retention_enabled"), False, "retention_enabled")
        self.include_movies = _strict_bool(
            get("retention_include_movies"), False, "retention_include_movies"
        )
        self.include_episodes = _strict_bool(
            get("retention_include_episodes"), False, "retention_include_episodes"
        )
        self.watched_only = _strict_bool(
            get("retention_watched_only"), True, "retention_watched_only"
        )
        self.use_added_age = _strict_bool(
            get("retention_use_added_age"), True, "retention_use_added_age"
        )
        self.added_age_days = _strict_int(
            get("retention_added_age_days"), 30, 0, 9999, "retention_added_age_days"
        )
        self.use_watched_age = _strict_bool(
            get("retention_use_watched_age"), True, "retention_use_watched_age"
        )
        self.watched_age_days = _strict_int(
            get("retention_watched_age_days"), 30, 0, 9999, "retention_watched_age_days"
        )
        self.criteria_mode = _strict_choice(
            get("retention_criteria_mode"), "all", {"all", "any"}, "retention_criteria_mode"
        )
        self.movie_rating_threshold = _strict_float(
            get("retention_movie_rating_threshold"),
            0.0,
            0.0,
            10.0,
            "retention_movie_rating_threshold",
        )
        self.exclusions = parse_exclusions(get("retention_exclusions"))
        self.manual_dry_run = _strict_bool(
            get("retention_manual_dry_run"), True, "retention_manual_dry_run"
        )
        self.periodic_enabled = _strict_bool(
            get("retention_periodic_enabled"), False, "retention_periodic_enabled"
        )
        self.interval_hours = _strict_int(
            get("retention_interval_hours"), 24, 1, 720, "retention_interval_hours"
        )
        self.max_deletions = _strict_int(
            get("retention_max_deletions"), 5, 1, 100, "retention_max_deletions"
        )
        self.background_dry_run = _strict_bool(
            get("retention_background_dry_run"), True, "retention_background_dry_run"
        )
        self.notification_mode = _strict_choice(
            get("retention_notification_mode"),
            "errors_only",
            {"errors_only", "deletions_and_errors", "silent"},
            "retention_notification_mode",
        )

    def validate(self):
        if not self.enabled:
            raise ConfigurationError("Retention is disabled in add-on settings.")
        if not self.include_movies and not self.include_episodes:
            raise ConfigurationError("Retention requires movies and/or episodes to be included.")
        if not self.use_added_age and not self.use_watched_age:
            raise ConfigurationError("Retention requires at least one age criterion.")
        return self
