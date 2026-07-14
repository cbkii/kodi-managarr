from .models import HistoryMatch
from .util import normalise_path, normalise_release


def match_history(records, file_record, episode_ids=None):
    """Find the imported-history event most likely to represent a current file."""
    episode_ids = {int(x) for x in (episode_ids or [])}
    relative = file_record.get("relativePath") or file_record.get("path") or ""
    scene_name = file_record.get("sceneName") or ""
    wanted_names = {normalise_release(relative), normalise_release(scene_name)} - {""}
    wanted_path = normalise_path(file_record.get("path") or relative)
    matches = []

    for record in records or []:
        score = 0
        reasons = []
        data = record.get("data") or {}
        source_title = record.get("sourceTitle") or ""
        record_names = {
            normalise_release(source_title),
            normalise_release(data.get("importedPath")),
            normalise_release(data.get("droppedPath")),
            normalise_release(data.get("relativePath")),
        } - {""}
        if wanted_names & record_names:
            score += 120
            reasons.append("release/file name")

        for key in ("importedPath", "droppedPath", "path"):
            candidate = normalise_path(data.get(key) or "")
            if candidate and wanted_path and (candidate == wanted_path or candidate.endswith("/" + wanted_path.split("/")[-1])):
                score += 100
                reasons.append(key)
                break

        episode_id = int(record.get("episodeId") or 0)
        if episode_ids and episode_id in episode_ids:
            score += 35
            reasons.append("episode")
        if record.get("downloadId"):
            score += 10
            reasons.append("download ID")
        if source_title:
            score += 5

        if score:
            matches.append(
                HistoryMatch(
                    history_id=int(record["id"]),
                    source_title=source_title or "Unknown release",
                    download_id=str(record.get("downloadId") or ""),
                    score=score,
                    reason=", ".join(reasons),
                )
            )

    matches.sort(key=lambda match: match.score, reverse=True)
    if not matches or matches[0].score < 80:
        return None
    if len(matches) > 1 and matches[0].score == matches[1].score and matches[0].download_id != matches[1].download_id:
        return None
    return matches[0]


def unique_history_matches(matches):
    output = []
    seen = set()
    for match in matches:
        if not match:
            continue
        key = match.download_id or f"history:{match.history_id}"
        if key in seen:
            continue
        seen.add(key)
        output.append(match)
    return output
