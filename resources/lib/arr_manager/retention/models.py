# SPDX-License-Identifier: GPL-3.0-or-later
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class RetentionCandidate:
    media_type: str
    db_id: int
    arr_id: int
    file_id: Optional[int]
    title: str
    display_name: str
    watched: bool
    last_played: Optional[float]
    date_added: Optional[float]
    unique_ids: Dict[str, str] = field(default_factory=dict)
    season: Optional[int] = None
    episode: Optional[int] = None
    file_path: str = ""
    tvshow_db_id: int = 0
    series_title: str = ""
    rating: Optional[float] = None


@dataclass
class RetentionEligibility:
    eligible: bool
    reason: str
    passed_rules: List[str] = field(default_factory=list)
    failed_rules: List[str] = field(default_factory=list)


@dataclass
class RetentionReportItem:
    media_type: str
    display_name: str
    db_id: int
    eligible: bool
    reason: str
    action_taken: str
    error_message: str = ""
