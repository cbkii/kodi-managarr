# SPDX-License-Identifier: GPL-3.0-or-later
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class RetentionCandidate:
    media_type: str
    kodi_db_ids: Tuple[int, ...]
    arr_id: int
    file_id: int
    title: str
    display_name: str
    watched: bool
    last_played: Optional[float]
    date_added: Optional[float]
    unique_ids: Dict[str, str] = field(default_factory=dict)
    linked_episode_ids: Tuple[int, ...] = ()
    season: int = -1
    episode: int = -1
    tvshow_title: str = ""
    file_path: str = ""

    @property
    def stable_key(self):
        return f"{self.media_type}:{self.arr_id}:{self.file_id}"

    @property
    def primary_kodi_id(self):
        return self.kodi_db_ids[0] if self.kodi_db_ids else 0

    def identity_tuple(self):
        return (
            self.media_type,
            tuple(self.kodi_db_ids),
            int(self.arr_id),
            int(self.file_id),
            tuple(self.linked_episode_ids),
        )

    def state_tuple(self):
        return (
            bool(self.watched),
            round(float(self.last_played or 0.0), 3),
            round(float(self.date_added or 0.0), 3),
        )


@dataclass(frozen=True)
class RetentionEligibility:
    eligible: bool
    reason: str
    passed_rules: Tuple[str, ...] = ()
    failed_rules: Tuple[str, ...] = ()
    added_age_days: Optional[int] = None
    watched_age_days: Optional[int] = None


@dataclass(frozen=True)
class RetentionScanResult:
    candidate: Optional[RetentionCandidate] = None
    skipped_reason: str = ""


@dataclass
class RetentionReportItem:
    media_type: str
    display_name: str
    stable_key: str
    kodi_db_ids: List[int]
    arr_id: int
    file_id: int
    eligible: bool
    reason: str
    action_taken: str
    error_type: str = ""
    committed: bool = False
    stages: List[str] = field(default_factory=list)
