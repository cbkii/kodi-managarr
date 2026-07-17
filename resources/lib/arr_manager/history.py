# SPDX-License-Identifier: GPL-3.0-or-later
from .models import HistoryMatch
from .util import normalise_optional_path, normalise_release, paths_equal


def match_history(records, file_record, episode_ids=None):
    episode_ids = {int(value) for value in (episode_ids or [])}
    relative = file_record.get("relativePath") or file_record.get("path") or ""
    scene_name = file_record.get("sceneName") or ""
    wanted_names = {normalise_release(relative), normalise_release(scene_name)} - {""}
    wanted_path = normalise_optional_path(file_record.get("path") or "")
    matches = []
    for record in records or []:
        if not isinstance(record, dict):
            continue
        score, reasons = 0, []
        data = record.get("data") if isinstance(record.get("data"), dict) else {}
        source_title = record.get("sourceTitle") or ""
        record_names = {
            normalise_release(source_title), normalise_release(data.get("importedPath")),
            normalise_release(data.get("droppedPath")), normalise_release(data.get("relativePath")),
        } - {""}
        if wanted_names and wanted_names & record_names:
            score += 120; reasons.append("release/file name")
        for key in ("importedPath", "droppedPath", "path"):
            candidate = normalise_optional_path(data.get(key) or "")
            if candidate and wanted_path and paths_equal(candidate, wanted_path):
                score += 140; reasons.append(key); break
        episode_id = int(record.get("episodeId") or 0)
        if episode_ids and episode_id in episode_ids:
            score += 35; reasons.append("episode")
        download_id = str(record.get("downloadId") or "")
        if download_id:
            score += 10; reasons.append("download ID")
        if source_title:
            score += 5
        try:
            history_id = int(record.get("id") or 0)
        except (TypeError, ValueError):
            history_id = 0
        if score and history_id > 0:
            matches.append(HistoryMatch(history_id, source_title or "Unknown release", download_id, score, ", ".join(reasons)))
    matches.sort(key=lambda match: match.score, reverse=True)
    if not matches or matches[0].score < 80:
        return None
    if len(matches) > 1 and matches[0].score == matches[1].score and matches[0].download_id != matches[1].download_id:
        return None
    return matches[0]


def unique_history_matches(matches):
    output, seen = [], set()
    for match in matches:
        if not match:
            continue
        key = match.download_id or f"history:{match.history_id}"
        if key not in seen:
            seen.add(key); output.append(match)
    return output
