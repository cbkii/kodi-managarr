from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class SelectedItem:
    media_type: str
    db_id: int = 0
    title: str = ""
    year: int = 0
    tvshow_title: str = ""
    season: int = -1
    episode: int = -1
    file_path: str = ""
    unique_ids: Dict[str, str] = field(default_factory=dict)

    @property
    def display_name(self) -> str:
        if self.media_type == "episode":
            prefix = self.tvshow_title or self.title
            return f"{prefix} S{self.season:02d}E{self.episode:02d}"
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
class ActionResult:
    title: str
    message: str
    details: Optional[dict] = None
