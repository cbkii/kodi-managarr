# SPDX-License-Identifier: GPL-3.0-or-later
from dataclasses import dataclass, field
from typing import List, Optional


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

    # Internal stable unique IDs
    unique_ids: dict = field(default_factory=dict)

    # Episode specific identifying info
    season: Optional[int] = None
    episode: Optional[int] = None
    file_path: str = ""

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
    action_taken: str # "deleted", "skipped", "failed", "dry_run"
    error_message: str = ""
