# SPDX-License-Identifier: GPL-3.0-or-later
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(frozen=True)
class RetentionCandidate:
    media_type: str
    db_id: int
    arr_id: int
    file_id: int
    title: str
    display_name: str
    watched: bool
    last_played: Optional[float]
    date_added: Optional[float]
    unique_ids: Dict[str, str] = field(default_factory=dict)
    series_tvdb_id: int = 0
    season: int = -1
    episode: int = -1
    rating: Optional[float] = None
    rating_sources: Dict[str, float] = field(default_factory=dict)

    @property
    def stable_key(self):
        if self.media_type == "movie":
            tmdb = str(self.unique_ids.get("tmdb") or "").strip()
            return f"movie:tmdb:{tmdb}" if tmdb else f"movie:radarr:{self.arr_id}"
        return f"episode:sonarr:{self.file_id}"

    @property
    def series_key(self):
        if self.series_tvdb_id > 0:
            return f"series:tvdb:{self.series_tvdb_id}"
        return f"series:sonarr:{self.arr_id}"

    @property
    def season_key(self):
        return f"{self.series_key}:season:{self.season}"


@dataclass(frozen=True)
class RetentionEligibility:
    eligible: bool
    reason: str
    passed_rules: List[str] = field(default_factory=list)
    failed_rules: List[str] = field(default_factory=list)
    added_age_days: Optional[int] = None
    watched_age_days: Optional[int] = None


@dataclass
class RetentionReportItem:
    media_type: str
    display_name: str
    db_id: int
    eligible: bool
    reason: str
    action_taken: str
    stages: List[str] = field(default_factory=list)
    error_type: str = ""

    def as_dict(self):
        return {
            "media_type": self.media_type,
            "display_name": self.display_name[:200],
            "db_id": int(self.db_id),
            "eligible": bool(self.eligible),
            "reason": self.reason[:300],
            "action_taken": self.action_taken,
            "stages": list(self.stages),
            "error_type": self.error_type,
        }
