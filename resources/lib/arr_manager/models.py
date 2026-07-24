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

    def effective_unique_ids(self) -> Dict[str, str]:
        if self.media_type == "episode":
            return self.series_unique_ids or {}
        return self.unique_ids or {}

    def effective_year(self) -> int:
        value = self.series_year if self.media_type == "episode" else self.year
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

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
    current_stage: str = "preflight"
    command_id: int = 0
    command_description: str = ""
    command_status: str = ""
    command_result: str = ""

    def begin(self, stage: str) -> None:
        self.current_stage = str(stage or "unknown stage")

    def mark(self, stage: str, committed: bool = False) -> None:
        self.current_stage = str(stage or self.current_stage)
        if stage not in self.stages:
            self.stages.append(stage)
        self.committed = self.committed or committed

    def record_command(self, description: str, command: dict) -> None:
        command = command if isinstance(command, dict) else {}
        try:
            self.command_id = int(command.get("id") or 0)
        except (TypeError, ValueError):
            self.command_id = 0
        self.command_description = str(description or "")
        self.command_status = str(command.get("status") or "")
        self.command_result = str(command.get("result") or "")

    def failure_message(self, exc: Exception) -> str:
        completed = ", ".join(self.stages) if self.stages else "preflight only"
        prefix = "Partial operation" if self.committed else "Operation stopped before destructive commit"
        return (
            f"{prefix}. Failed stage: {self.current_stage}. Completed stages: {completed}. "
            f"Failure type: {type(exc).__name__}. Review diagnostics and kodi.log before retrying."
        )

    def as_dict(self, exc: Optional[Exception] = None) -> dict:
        payload = {
            "operation": self.operation,
            "stages": list(self.stages),
            "committed": bool(self.committed),
            "failedStage": self.current_stage if exc is not None else "",
            "errorType": type(exc).__name__ if exc is not None else "",
            "status": "failed" if exc is not None else "completed",
            "commandId": self.command_id,
            "commandDescription": self.command_description,
            "commandStatus": self.command_status,
            "commandResult": self.command_result,
        }
        method = getattr(exc, "method", "") if exc is not None else ""
        code = getattr(exc, "code", None) if exc is not None else None
        safe_data = getattr(exc, "safe_data", {}) if exc is not None else {}
        if method:
            payload["kodiJsonRpcMethod"] = str(method)
        if isinstance(code, int):
            payload["kodiJsonRpcCode"] = code
        if isinstance(safe_data, dict) and safe_data:
            payload["kodiJsonRpcData"] = dict(safe_data)
        return payload
