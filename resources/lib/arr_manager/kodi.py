import json
import logging
import os
import sys
import traceback

from .models import SelectedItem
from .util import as_int, normalise_title, paths_equal, redact_url


class KodiLogger:
    def __init__(self, debug=False):
        import xbmc
        self.xbmc = xbmc
        self.debug_enabled = debug

    def _write(self, level, message, *args):
        if args:
            message = message % args
        self.xbmc.log(f"[Arr Manager] {message}", level)

    def debug(self, message, *args):
        if self.debug_enabled:
            self._write(self.xbmc.LOGDEBUG, message, *args)

    def info(self, message, *args):
        self._write(self.xbmc.LOGINFO, message, *args)

    def warning(self, message, *args):
        self._write(self.xbmc.LOGWARNING, message, *args)

    def error(self, message, *args):
        self._write(self.xbmc.LOGERROR, message, *args)

    def exception(self, message):
        self.error("%s\n%s", message, traceback.format_exc())


class KodiJsonRpcError(Exception):
    pass


class KodiJsonRpcClient:
    """Small validated wrapper around Kodi's JSON-RPC transport."""

    MOVIE_PROPERTIES = ["title", "year", "file", "uniqueid"]
    TVSHOW_PROPERTIES = ["title", "year", "uniqueid"]
    EPISODE_PROPERTIES = ["title", "season", "episode", "file", "tvshowid", "tvshowtitle"]

    def __init__(self, xbmc_module, logger=None):
        self.xbmc = xbmc_module
        self.logger = logger
        self._next_id = 1

    def call(self, method, params=None):
        request_id = self._next_id
        self._next_id += 1
        payload = {"jsonrpc": "2.0", "id": request_id, "method": method}
        if params is not None:
            payload["params"] = params
        raw = self.xbmc.executeJSONRPC(json.dumps(payload))
        try:
            response = json.loads(raw or "")
        except (TypeError, ValueError) as exc:
            raise KodiJsonRpcError("Kodi JSON-RPC returned malformed JSON") from exc
        if not isinstance(response, dict):
            raise KodiJsonRpcError("Kodi JSON-RPC response is not an object")
        error = response.get("error")
        if error:
            if isinstance(error, dict):
                raise KodiJsonRpcError(str(error.get("message") or error))
            raise KodiJsonRpcError("Kodi JSON-RPC returned a malformed error")
        if response.get("id") != request_id:
            raise KodiJsonRpcError("Kodi JSON-RPC response ID did not match the request")
        if "result" not in response:
            raise KodiJsonRpcError("Kodi JSON-RPC response did not contain a result")
        return response["result"]

    @staticmethod
    def _detail(result, key):
        if not isinstance(result, dict) or not isinstance(result.get(key), dict):
            raise KodiJsonRpcError(f"Kodi JSON-RPC returned malformed {key}")
        return result[key]

    @staticmethod
    def _items(result, key):
        if not isinstance(result, dict):
            raise KodiJsonRpcError("Kodi JSON-RPC returned a malformed list result")
        items = result.get(key, [])
        if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
            raise KodiJsonRpcError(f"Kodi JSON-RPC returned malformed {key}")
        return items

    def movie_details(self, movie_id):
        result = self.call(
            "VideoLibrary.GetMovieDetails",
            {"movieid": int(movie_id), "properties": self.MOVIE_PROPERTIES},
        )
        return self._detail(result, "moviedetails")

    def movies(self):
        result = self.call("VideoLibrary.GetMovies", {"properties": self.MOVIE_PROPERTIES})
        return self._items(result, "movies")

    def tvshow_details(self, tvshow_id):
        result = self.call(
            "VideoLibrary.GetTVShowDetails",
            {"tvshowid": int(tvshow_id), "properties": self.TVSHOW_PROPERTIES},
        )
        return self._detail(result, "tvshowdetails")

    def tvshows(self):
        result = self.call("VideoLibrary.GetTVShows", {"properties": self.TVSHOW_PROPERTIES})
        return self._items(result, "tvshows")

    def episode_details(self, episode_id):
        result = self.call(
            "VideoLibrary.GetEpisodeDetails",
            {"episodeid": int(episode_id), "properties": self.EPISODE_PROPERTIES},
        )
        return self._detail(result, "episodedetails")

    def episodes(self, tvshow_id):
        if int(tvshow_id or 0) <= 0:
            raise KodiJsonRpcError("A validated Kodi TV show ID is required for targeted episode cleanup")
        result = self.call(
            "VideoLibrary.GetEpisodes",
            {"tvshowid": int(tvshow_id), "properties": self.EPISODE_PROPERTIES},
        )
        return self._items(result, "episodes")

    def remove_movie(self, movie_id):
        if int(movie_id or 0) <= 0:
            raise KodiJsonRpcError("A valid Kodi movie ID is required for targeted cleanup")
        return self.call("VideoLibrary.RemoveMovie", {"movieid": int(movie_id)})

    def remove_tvshow(self, tvshow_id):
        if int(tvshow_id or 0) <= 0:
            raise KodiJsonRpcError("A valid Kodi TV show ID is required for targeted cleanup")
        return self.call("VideoLibrary.RemoveTVShow", {"tvshowid": int(tvshow_id)})

    def remove_episode(self, episode_id):
        if int(episode_id or 0) <= 0:
            raise KodiJsonRpcError("A valid Kodi episode ID is required for targeted cleanup")
        return self.call("VideoLibrary.RemoveEpisode", {"episodeid": int(episode_id)})


class KodiUI:
    def __init__(self, addon):
        import xbmc
        import xbmcgui
        self.xbmc = xbmc
        self.xbmcgui = xbmcgui
        self.addon = addon
        self.name = addon.getAddonInfo("name")
        self.jsonrpc = KodiJsonRpcClient(xbmc)

    def notification(self, message, error=False, milliseconds=5000):
        icon = self.xbmcgui.NOTIFICATION_ERROR if error else self.xbmcgui.NOTIFICATION_INFO
        self.xbmcgui.Dialog().notification(self.name, message, icon, milliseconds)

    def ok(self, heading, message):
        return self.xbmcgui.Dialog().ok(heading, message)

    def confirm(self, heading, message):
        return self.xbmcgui.Dialog().yesno(heading, message, yeslabel="Continue", nolabel="Cancel")

    def select(self, heading, options):
        return self.xbmcgui.Dialog().select(heading, options)

    def progress(self, heading, message=""):
        dialog = self.xbmcgui.DialogProgress()
        dialog.create(heading, message)
        return dialog

    def open_settings(self):
        self.addon.openSettings()

    def refresh_kodi_library(self):
        raise KodiJsonRpcError("Targeted Kodi JSON-RPC synchronisation requires workflow context")

    def sync_deleted_movie(self, selected):
        movie_id = self._resolve_movie_id(selected)
        if movie_id is None:
            return {"status": "already_absent", "kind": "movie"}
        return {"status": "removed", "kind": "movie", "id": movie_id, "result": self.jsonrpc.remove_movie(movie_id)}

    def sync_deleted_series(self, selected):
        tvshow_id = self._resolve_tvshow_id(selected)
        if tvshow_id is None:
            return {"status": "already_absent", "kind": "tvshow"}
        return {"status": "removed", "kind": "tvshow", "id": tvshow_id, "result": self.jsonrpc.remove_tvshow(tvshow_id)}

    def sync_deleted_episodes(self, selected, linked=None, file_paths=None):
        linked = list(linked or [])
        target_paths = [path for path in (file_paths or []) if path]
        if getattr(selected, "file_path", ""):
            target_paths.append(selected.file_path)

        episode_ids = []
        tvshow_id = 0
        if selected.media_type == "episode" and int(getattr(selected, "db_id", 0) or 0) > 0:
            try:
                detail = self.jsonrpc.episode_details(selected.db_id)
            except KodiJsonRpcError:
                detail = None
            if detail and self._episode_matches_selected(detail, selected):
                episode_ids.append(int(detail.get("episodeid") or selected.db_id))
                tvshow_id = int(detail.get("tvshowid") or 0)

        if selected.media_type == "tvshow" and int(getattr(selected, "db_id", 0) or 0) > 0:
            tvshow_id = self._resolve_tvshow_id(selected) or 0
        if not tvshow_id:
            tvshow_id = self._resolve_tvshow_id(selected, allow_absent=False) or 0

        target_numbers = {
            (int(item.get("seasonNumber", -999)), int(item.get("episodeNumber", -999)))
            for item in linked
            if isinstance(item, dict)
        }
        candidates = self.jsonrpc.episodes(tvshow_id)
        matched_numbers = set()
        for episode in candidates:
            episode_id = int(episode.get("episodeid") or 0)
            number = (int(episode.get("season", -999)), int(episode.get("episode", -999)))
            path_match = bool(target_paths) and any(_same_path(episode.get("file", ""), path) for path in target_paths)
            number_match = number in target_numbers
            if episode_id > 0 and (path_match or number_match):
                if episode_id not in episode_ids:
                    episode_ids.append(episode_id)
                if number_match:
                    matched_numbers.add(number)

        if not episode_ids:
            return {
                "status": "already_absent",
                "kind": "episodes",
                "targets": sorted(target_numbers),
            }

        results = []
        for episode_id in episode_ids:
            results.append({"id": episode_id, "result": self.jsonrpc.remove_episode(episode_id)})
        return {
            "status": "removed",
            "kind": "episodes",
            "removed": results,
            "already_absent": sorted(target_numbers - matched_numbers),
        }

    def _resolve_movie_id(self, selected):
        db_id = int(getattr(selected, "db_id", 0) or 0)
        if db_id > 0:
            try:
                details = self.jsonrpc.movie_details(db_id)
            except KodiJsonRpcError:
                details = None
            if details and _movie_matches(details, selected, require_strong=False):
                return int(details.get("movieid") or db_id)

        candidates = [item for item in self.jsonrpc.movies() if _movie_matches(item, selected, require_strong=True)]
        if len(candidates) > 1:
            raise KodiJsonRpcError("Multiple Kodi movie rows matched the deleted media")
        if candidates:
            return int(candidates[0].get("movieid") or 0)
        if _movie_has_strong_identity(selected):
            return None
        raise KodiJsonRpcError("Could not safely resolve the Kodi movie row for targeted cleanup")

    def _resolve_tvshow_id(self, selected, allow_absent=True):
        db_id = int(getattr(selected, "db_id", 0) or 0) if selected.media_type == "tvshow" else 0
        if db_id > 0:
            try:
                details = self.jsonrpc.tvshow_details(db_id)
            except KodiJsonRpcError:
                details = None
            if details and _tvshow_matches(details, selected, require_strong=False):
                return int(details.get("tvshowid") or db_id)

        candidates = [item for item in self.jsonrpc.tvshows() if _tvshow_matches(item, selected, require_strong=True)]
        if len(candidates) > 1:
            raise KodiJsonRpcError("Multiple Kodi TV show rows matched the deleted media")
        if candidates:
            return int(candidates[0].get("tvshowid") or 0)
        if allow_absent and _tvshow_has_strong_identity(selected):
            return None
        raise KodiJsonRpcError("Could not safely resolve the Kodi TV show row for targeted cleanup")

    @staticmethod
    def _episode_matches_selected(details, selected):
        if int(details.get("season", -999)) != int(getattr(selected, "season", -998)):
            return False
        if int(details.get("episode", -999)) != int(getattr(selected, "episode", -998)):
            return False
        selected_show = normalise_title(getattr(selected, "tvshow_title", "") or getattr(selected, "title", ""))
        detail_show = normalise_title(details.get("tvshowtitle", ""))
        if selected_show and detail_show and selected_show != detail_show:
            return False
        selected_path = getattr(selected, "file_path", "")
        detail_path = details.get("file", "")
        if selected_path and detail_path and not _same_path(selected_path, detail_path):
            return False
        return True

    def wait_for_abort(self, seconds):
        return self.xbmc.Monitor().waitForAbort(float(seconds))


def _tag_value(tag, method, default=""):
    try:
        fn = getattr(tag, method)
        value = fn()
        return default if value is None else value
    except Exception:
        return default


def _first_present(*values, invalid=None):
    invalid_values = {str(value) for value in (invalid or ())}
    for value in values:
        if value is None or value == "":
            continue
        if str(value) in invalid_values:
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
    return bool(getattr(selected, "unique_ids", {})) or bool(
        (getattr(selected, "tvshow_title", "") or getattr(selected, "title", ""))
        and int(getattr(selected, "year", 0) or 0)
    )


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
    import xbmcgui

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
        season=as_int(_first_present(_tag_value(tag, "getSeason", "") if tag else "", label("ListItem.Season"), invalid=(-1, "-1")), -1),
        episode=as_int(_first_present(_tag_value(tag, "getEpisode", "") if tag else "", label("ListItem.Episode"), invalid=(-1, "-1")), -1),
        file_path=str(file_path),
        unique_ids=unique_ids,
    )
