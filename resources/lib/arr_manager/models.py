# SPDX-License-Identifier: GPL-3.0-or-later
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class SelectedItem:
    media_type: str
    db_id: int = 0
    title: str = ""
    year: int = 0
    tvshow_title: str = ""
    tvshow_db_id: int = 0
    season: int = -1
    episode: int = -1
    file_path: str = ""
    unique_ids: Dict[str, str] = field(default_factory=dict)
    series_year: int = 0
    series_unique_ids: Dict[str, str] = field(default_factory=dict)

    @property
    def display_name(self) -> str:
        if self.media_type == "episode":
            prefix = self.tvshow_title or self.title
            if self.season >= 0 and self.episode >= 0:
                return f"{prefix} S{self.season:02d}E{self.episode:02d}"
            return prefix
        year = f" ({self.year})" if self.year else ""
        return f"{self.title}{year}"


@dataclass
class HistoryMatch:
    history_id: int
    source_title: str
    download_id: str = ""
    score: int = 0
    reason: str = ""


@dataclass
class TransactionState:
    operation: str
    stages: List[str] = field(default_factory=list)
    committed: bool = False

    def mark(self, stage: str, committed: bool = False) -> None:
        if stage not in self.stages:
            self.stages.append(stage)
        self.committed = self.committed or committed

    def failure_message(self, exc: Exception) -> str:
        completed = ", ".join(self.stages) if self.stages else "preflight only"
        prefix = "Partial operation" if self.committed else "Operation stopped before destructive commit"
        return (
            f"{prefix}. Completed stages: {completed}. Failure type: {type(exc).__name__}. "
            "Review diagnostics and kodi.log before retrying."
        )

    def as_dict(self, exc: Optional[Exception] = None) -> dict:
        return {
            "operation": self.operation,
            "stages": list(self.stages),
            "committed": bool(self.committed),
            "errorType": type(exc).__name__ if exc is not None else "",
            "status": "failed" if exc is not None else "completed",
        }
