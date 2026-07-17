# SPDX-License-Identifier: GPL-3.0-or-later
import sys

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


def _tvshow_has_strong_identity(selected):
    return bool(getattr(selected, "unique_ids", {})) or bool((getattr(selected, "tvshow_title", "") or getattr(selected, "title", "")) and int(getattr(selected, "year", 0) or 0))


def _tvshow_matches(details, selected, require_strong):
    title = normalise_title(details.get("title", ""))
    selected_title = normalise_title(getattr(selected, "tvshow_title", "") or getattr(selected, "title", ""))
    if title and selected_title and title != selected_title:
        return False
    year = int(details.get("year") or 0)
    selected_year = int(getattr(selected, "year", 0) or 0)
    if year and selected_year and year != selected_year:
        return False
    unique_state = _unique_id_state(getattr(selected, "unique_ids", {}), details.get("uniqueid"))
    if unique_state == "contradiction":
        return False
    strong = unique_state == "match" or bool(title and selected_title and year and selected_year)
    return strong if require_strong else True


def selected_item_from_context():
    import xbmc
    import xbmcgui  # noqa: F401
    item = getattr(sys, "listitem", None)
    tag = None
    if item is not None:
        try:
            tag = item.getVideoInfoTag()
        except Exception:
            tag = None

    def label(name):
        try:
            return xbmc.getInfoLabel(name) or ""
        except Exception:
            return ""

    unique_ids = {}
    for key in ("tmdb", "tvdb", "imdb"):
        value = ""
        if tag is not None:
            try:
                value = tag.getUniqueID(key) or ""
            except Exception:
                pass
        value = value or label(f"ListItem.UniqueID({key})")
        if value:
            unique_ids[key] = str(value)
    media_type = (_tag_value(tag, "getMediaType") if tag else "") or label("ListItem.DBType")
    title = (_tag_value(tag, "getTitle") if tag else "") or label("ListItem.Title")
    tvshow_title = (_tag_value(tag, "getTVShowTitle") if tag else "") or label("ListItem.TVShowTitle")
    file_path = ""
    if tag is not None:
        file_path = _tag_value(tag, "getFilenameAndPath") or _tag_value(tag, "getPath")
    if not file_path and item is not None:
        try:
            file_path = item.getPath() or ""
        except Exception:
            file_path = ""
    file_path = file_path or label("ListItem.FileNameAndPath")
    return SelectedItem(
        media_type=str(media_type).lower(),
        db_id=as_int(_first_present(_tag_value(tag, "getDbId", "") if tag else "", label("ListItem.DBID"), invalid=(0, "0")), 0),
        title=str(title),
        year=as_int(_first_present(_tag_value(tag, "getYear", "") if tag else "", label("ListItem.Year"), invalid=(0, "0")), 0),
        tvshow_title=str(tvshow_title),
        tvshow_db_id=as_int(label("ListItem.TVShowDBID"), 0),
        season=as_int(_first_present(_tag_value(tag, "getSeason", "") if tag else "", label("ListItem.Season"), invalid=(-1, "-1")), -1),
        episode=as_int(_first_present(_tag_value(tag, "getEpisode", "") if tag else "", label("ListItem.Episode"), invalid=(-1, "-1")), -1),
        file_path=str(file_path),
        unique_ids=unique_ids,
    )
