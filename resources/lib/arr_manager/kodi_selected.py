# SPDX-License-Identifier: GPL-3.0-or-later
import sys

from .kodi_jsonrpc import KodiJsonRpcError
from .models import SelectedItem
from .util import as_int, normalise_title, paths_equal


def _tag_value(tag, method, default=""):
    try:
        value = getattr(tag, method)()
        return default if value is None else value
    except Exception:
        return default


def _first_present(*values, invalid=None):
    invalid_values = {str(value) for value in (invalid or ())}
    for value in values:
        if value is None or value == "" or str(value) in invalid_values:
            continue
        return value
    return ""


def _same_path(left, right):
    if not left or not right:
        return False
    try:
        return paths_equal(left, right)
    except ValueError:
        return False


def _unique_id_state(selected_ids, details_ids):
    selected_ids = selected_ids or {}
    details_ids = details_ids if isinstance(details_ids, dict) else {}
    compared = False
    matched = False
    for key, selected_value in selected_ids.items():
        detail_value = details_ids.get(key)
        if not selected_value or not detail_value:
            continue
        compared = True
        if str(selected_value) != str(detail_value):
            return "contradiction"
        matched = True
    if matched:
        return "match"
    return "unknown" if not compared else "contradiction"


def _movie_has_strong_identity(selected):
    return bool(getattr(selected, "file_path", "") or getattr(selected, "unique_ids", {}))


def _movie_matches(details, selected, require_strong):
    title = normalise_title(details.get("title", ""))
    selected_title = normalise_title(getattr(selected, "title", ""))
    if title and selected_title and title != selected_title:
        return False
    year = int(details.get("year") or 0)
    selected_year = int(getattr(selected, "year", 0) or 0)
    if year and selected_year and year != selected_year:
        return False
    detail_path = details.get("file", "")
    selected_path = getattr(selected, "file_path", "")
    if detail_path and selected_path and not _same_path(detail_path, selected_path):
        return False
    unique_state = _unique_id_state(getattr(selected, "unique_ids", {}), details.get("uniqueid"))
    if unique_state == "contradiction":
        return False
    strong = bool(detail_path and selected_path and _same_path(detail_path, selected_path)) or unique_state == "match"
    return strong if require_strong else True


def _series_unique_ids(selected):
    if getattr(selected, "media_type", "") == "episode":
        return getattr(selected, "series_unique_ids", {}) or {}
    return getattr(selected, "unique_ids", {}) or {}


def _series_year(selected):
    if getattr(selected, "media_type", "") == "episode":
        return int(getattr(selected, "series_year", 0) or 0)
    return int(getattr(selected, "year", 0) or 0)


def _tvshow_has_strong_identity(selected):
    return bool(_series_unique_ids(selected)) or bool(
        (getattr(selected, "tvshow_title", "") or getattr(selected, "title", "")) and _series_year(selected)
    )


def _tvshow_matches(details, selected, require_strong):
    title = normalise_title(details.get("title", ""))
    selected_title = normalise_title(getattr(selected, "tvshow_title", "") or getattr(selected, "title", ""))
    if title and selected_title and title != selected_title:
        return False
    year = int(details.get("year") or 0)
    selected_year = _series_year(selected)
    if year and selected_year and year != selected_year:
        return False
    unique_state = _unique_id_state(_series_unique_ids(selected), details.get("uniqueid"))
    if unique_state == "contradiction":
        return False
    strong = unique_state == "match" or bool(title and selected_title and year and selected_year)
    return strong if require_strong else True


def _get_listitem():
    return getattr(sys, "listitem", None)


def _get_video_tag(item):
    if item is not None:
        try:
            return item.getVideoInfoTag()
        except Exception:
            return None
    return None


def _get_label(name):
    import xbmc
    try:
        return xbmc.getInfoLabel(name) or ""
    except Exception:
        return ""


def _extract_unique_ids(tag):
    unique_ids = {}
    for key in ("tmdb", "tvdb", "imdb"):
        value = ""
        if tag is not None:
            try:
                value = tag.getUniqueID(key) or ""
            except Exception:
                pass
        value = value or _get_label(f"ListItem.UniqueID({key})")
        if value:
            unique_ids[key] = str(value)
    return unique_ids


def _extract_file_path(item, tag):
    file_path = ""
    if tag is not None:
        file_path = _tag_value(tag, "getFilenameAndPath") or _tag_value(tag, "getPath")
    if not file_path and item is not None:
        try:
            file_path = item.getPath() or ""
        except Exception:
            file_path = ""
    return file_path or _get_label("ListItem.FileNameAndPath")


def selected_item_from_context():
    import xbmcgui  # noqa: F401
    item = _get_listitem()
    tag = _get_video_tag(item)
    unique_ids = _extract_unique_ids(tag)
    media_type = (_tag_value(tag, "getMediaType") if tag else "") or _get_label("ListItem.DBType")
    title = (_tag_value(tag, "getTitle") if tag else "") or _get_label("ListItem.Title")
    tvshow_title = (_tag_value(tag, "getTVShowTitle") if tag else "") or _get_label("ListItem.TVShowTitle")
    file_path = _extract_file_path(item, tag)

    return SelectedItem(
        media_type=str(media_type).lower(),
        db_id=as_int(_first_present(_tag_value(tag, "getDbId", "") if tag else "", _get_label("ListItem.DBID"), invalid=(0, "0")), 0),
        title=str(title),
        year=as_int(_first_present(_tag_value(tag, "getYear", "") if tag else "", _get_label("ListItem.Year"), invalid=(0, "0")), 0),
        tvshow_title=str(tvshow_title),
        tvshow_db_id=as_int(_get_label("ListItem.TVShowDBID"), 0),
        season=as_int(_first_present(_tag_value(tag, "getSeason", "") if tag else "", _get_label("ListItem.Season"), invalid=(-1, "-1")), -1),
        episode=as_int(_first_present(_tag_value(tag, "getEpisode", "") if tag else "", _get_label("ListItem.Episode"), invalid=(-1, "-1")), -1),
        file_path=str(file_path),
        unique_ids=unique_ids,
    )


def enrich_selected_series_identity(selected, kodi_client):
    """Populate an episode's parent-series identity from Kodi JSON-RPC when available."""
    if not selected or selected.media_type != "episode":
        return selected
    tvshow_id = int(getattr(selected, "tvshow_db_id", 0) or 0)
    if tvshow_id <= 0 and int(getattr(selected, "db_id", 0) or 0) > 0:
        try:
            episode = kodi_client.episode_details(selected.db_id)
        except KodiJsonRpcError:
            episode = {}
        if isinstance(episode, dict):
            tvshow_id = int(episode.get("tvshowid") or 0)
            selected.tvshow_db_id = tvshow_id
            selected.tvshow_title = selected.tvshow_title or str(episode.get("tvshowtitle") or "")
    if tvshow_id <= 0:
        return selected
    try:
        details = kodi_client.tvshow_details(tvshow_id)
    except KodiJsonRpcError:
        return selected
    selected.tvshow_title = selected.tvshow_title or str(details.get("title") or "")
    selected.series_year = int(details.get("year") or 0)
    unique_ids = details.get("uniqueid")
    selected.series_unique_ids = {
        str(key): str(value) for key, value in (unique_ids.items() if isinstance(unique_ids, dict) else ()) if value
    }
    return selected
