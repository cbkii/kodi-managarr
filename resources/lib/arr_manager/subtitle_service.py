# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
import os
import re
import time
from urllib.parse import urlencode

from .actions import ArrManager
from .errors import ConfigurationError, ResolutionError, SafetyError
from .interactive_messages import imessage
from .models import SelectedItem
from .resolver import resolve_episode, resolve_movie, resolve_series

CACHE_TOKEN_RE = re.compile(r"^[a-f0-9]{32}$")
SUBTITLE_SUFFIXES = (".srt", ".ass", ".ssa", ".sub", ".vtt")
CACHE_MAX_AGE = 15 * 60


def _positive_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _language_code(row):
    value = row.get("language")
    if isinstance(value, dict):
        value = value.get("code2") or value.get("code3") or value.get("code") or value.get("name")
    value = value or row.get("language_code") or row.get("code2") or row.get("code3") or row.get("code")
    return str(value or "").strip().lower()


def _language_key(row):
    code = _language_code(row)
    if not code or ":" in code:
        return code
    if row.get("forced"):
        return code + ":forced"
    if row.get("hearing_impaired") or row.get("hi"):
        return code + ":hi"
    return code


def _release_match(row):
    value = row.get("release_info") or row.get("matches") or ""
    if isinstance(value, (list, tuple, set)):
        value = ", ".join(str(item) for item in value if item)
    elif isinstance(value, dict):
        value = ", ".join(str(key) for key, matched in value.items() if matched)
    value = " ".join(str(value or "").split())
    return value[:120]


def _result_label(addon, row, language):
    flags = []
    if row.get("forced"):
        flags.append(imessage(addon, "subtitle_forced"))
    if row.get("hearing_impaired") or row.get("hi"):
        flags.append(imessage(addon, "subtitle_hi"))
    suffix = imessage(addon, "subtitle_flags", flags=", ".join(flags)) if flags else ""

    provider = str(row.get("provider") or imessage(addon, "subtitle_best_match"))
    details = [provider]
    if row.get("score") is not None:
        details.append(imessage(addon, "subtitle_score", score=row.get("score")))
    release_match = _release_match(row)
    if release_match:
        details.append(imessage(addon, "subtitle_release_match", match=release_match))
    return language, imessage(
        addon,
        "subtitle_result_label",
        language=language,
        provider=" - ".join(details),
        flags=suffix,
    )


def _safe_result(row):
    allowed = {
        "language", "language_code", "code", "code2", "code3", "provider", "score", "forced",
        "hearing_impaired", "hi", "subtitle", "original_format", "release_info", "matches",
    }
    result = {key: row.get(key) for key in allowed if key in row}
    if isinstance(result.get("language"), dict):
        result["language"] = {
            key: result["language"].get(key)
            for key in ("code", "code2", "code3", "name") if key in result["language"]
        }
    return result


def _select_results(rows, allowed_languages):
    allowed = [str(value).strip().lower() for value in allowed_languages if str(value).strip()]
    priority = {value: index for index, value in enumerate(allowed)}
    best = {}
    for row in rows:
        base = _language_code(row)
        if base not in priority:
            continue
        variant = _language_key(row)
        score = float(row.get("score") or 0)
        if variant not in best or score > best[variant][0]:
            best[variant] = (score, row)
    return [
        (variant, best[variant][1])
        for variant in sorted(best, key=lambda value: (priority[value.split(":", 1)[0]], value))
    ]


def selected_from_player(addon, xbmc_module, kodi_client):
    db_type = str(xbmc_module.getInfoLabel("VideoPlayer.DBTYPE") or "").strip().lower()
    db_id = _positive_int(xbmc_module.getInfoLabel("VideoPlayer.DBID"), 0)
    playing_file = str(xbmc_module.Player().getPlayingFile() or "")
    if db_type == "movie" and db_id > 0:
        result = kodi_client.call("VideoLibrary.GetMovieDetails", {
            "movieid": db_id, "properties": ["title", "year", "file", "uniqueid"],
        })
        detail = result.get("moviedetails") if isinstance(result, dict) else None
        if not isinstance(detail, dict):
            raise ResolutionError(imessage(addon, "subtitle_movie_metadata_missing"))
        return SelectedItem(
            media_type="movie", db_id=db_id, title=str(detail.get("title") or ""),
            year=_positive_int(detail.get("year"), 0), file_path=str(detail.get("file") or playing_file),
            unique_ids=dict(detail.get("uniqueid") or {}),
        )
    if db_type == "episode" and db_id > 0:
        result = kodi_client.call("VideoLibrary.GetEpisodeDetails", {
            "episodeid": db_id,
            "properties": ["title", "season", "episode", "file", "tvshowid", "tvshowtitle", "uniqueid"],
        })
        detail = result.get("episodedetails") if isinstance(result, dict) else None
        if not isinstance(detail, dict):
            raise ResolutionError(imessage(addon, "subtitle_episode_metadata_missing"))
        return SelectedItem(
            media_type="episode", db_id=db_id, title=str(detail.get("title") or ""),
            tvshow_title=str(detail.get("tvshowtitle") or ""), tvshow_db_id=_positive_int(detail.get("tvshowid"), 0),
            season=_positive_int(detail.get("season"), -1), episode=_positive_int(detail.get("episode"), -1),
            file_path=str(detail.get("file") or playing_file), unique_ids=dict(detail.get("uniqueid") or {}),
        )
    raise ResolutionError(imessage(addon, "subtitle_library_playback_required"))


class SubtitleService:
    def __init__(self, addon, settings, ui, logger, kodi_client, xbmcvfs_module):
        self.addon = addon
        self.settings = settings
        self.ui = ui
        self.logger = logger
        self.kodi = kodi_client
        self.xbmcvfs = xbmcvfs_module
        self.manager = ArrManager(settings, ui, logger)
        self.profile = self.xbmcvfs.translatePath(addon.getAddonInfo("profile"))
        os.makedirs(self.profile, exist_ok=True)

    def search(self, base_url):
        self.settings.bazarr.validate("Bazarr")
        if not self.settings.bazarr_languages:
            raise ConfigurationError(imessage(self.addon, "languages_required"))
        import xbmc
        selected = selected_from_player(self.addon, xbmc, self.kodi)
        if selected.media_type == "movie":
            movie = resolve_movie(selected, self.manager.radarr, self.settings.path_mapper)
            target = {"media_type": "movie", "radarr_id": int(movie["id"]), "playing_file": selected.file_path}
            rows = self.manager.bazarr.search_movie_subtitles(movie["id"])
        else:
            series = resolve_series(selected, self.manager.sonarr, self.settings.path_mapper)
            episode = resolve_episode(selected, self.manager.sonarr, series)
            target = {
                "media_type": "episode", "series_id": int(series["id"]), "episode_id": int(episode["id"]),
                "playing_file": selected.file_path,
            }
            rows = self.manager.bazarr.search_episode_subtitles(episode["id"])

        output = []
        for language, row in _select_results(rows, self.settings.bazarr_languages):
            payload = dict(target)
            payload.update({"language": language, "result": _safe_result(row), "created": int(time.time())})
            token = self._save_cache(payload)
            label, label2 = _result_label(self.addon, row, language)
            output.append({
                "label": label,
                "label2": label2,
                "url": f"{base_url}?{urlencode({'action': 'download', 'token': token})}",
            })
        return output

    def download(self, token):
        payload = self._load_cache(token)
        language = str(payload.get("language") or "").lower()
        if language.split(":", 1)[0] not in self.settings.bazarr_languages:
            raise SafetyError(imessage(self.addon, "subtitle_invalid_request"))
        playing_file = str(payload.get("playing_file") or "")
        before = set(self._subtitle_candidates(playing_file, language))
        result = payload.get("result")
        if payload.get("media_type") == "movie":
            response = self.manager.bazarr.download_movie_subtitle(payload.get("radarr_id"), language, result)
        elif payload.get("media_type") == "episode":
            response = self.manager.bazarr.download_episode_subtitle(
                payload.get("series_id"), payload.get("episode_id"), language, result,
            )
        else:
            raise SafetyError(imessage(self.addon, "subtitle_invalid_request"))

        response_path = self._response_path(response)
        if response_path:
            mapped = self._map_accessible_path(response_path)
            if mapped:
                self._delete_cache(token)
                return mapped
        deadline = time.monotonic() + 15
        last_candidates = before
        while time.monotonic() < deadline:
            candidates = set(self._subtitle_candidates(playing_file, language))
            last_candidates = candidates
            preferred = sorted(candidates - before) or sorted(candidates)
            if preferred:
                self._delete_cache(token)
                return preferred[-1]
            if self.ui.wait_for_abort(0.5):
                break
        if last_candidates:
            self._delete_cache(token)
            return sorted(last_candidates)[-1]
        raise SafetyError(imessage(self.addon, "subtitle_not_found"))

    def _save_cache(self, payload):
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
        token = hashlib.sha256(raw + os.urandom(16)).hexdigest()[:32]
        path = os.path.join(self.profile, f"subtitle-{token}.json")
        temporary = path + ".tmp"
        with open(temporary, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, sort_keys=True, separators=(",", ":"))
        os.replace(temporary, path)
        self._prune_cache()
        return token

    def _load_cache(self, token):
        if not CACHE_TOKEN_RE.fullmatch(str(token or "")):
            raise SafetyError(imessage(self.addon, "subtitle_invalid_request"))
        path = os.path.join(self.profile, f"subtitle-{token}.json")
        try:
            if time.time() - os.path.getmtime(path) > CACHE_MAX_AGE:
                raise SafetyError(imessage(self.addon, "subtitle_invalid_request"))
            with open(path, encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, ValueError) as exc:
            raise SafetyError(imessage(self.addon, "subtitle_invalid_request")) from exc
        if not isinstance(payload, dict):
            raise SafetyError(imessage(self.addon, "subtitle_invalid_request"))
        return payload

    def _delete_cache(self, token):
        try:
            os.remove(os.path.join(self.profile, f"subtitle-{token}.json"))
        except OSError:
            pass

    def _prune_cache(self):
        now = time.time()
        try:
            names = os.listdir(self.profile)
        except OSError:
            return
        for name in names:
            if not name.startswith("subtitle-") or not name.endswith(".json"):
                continue
            path = os.path.join(self.profile, name)
            try:
                if now - os.path.getmtime(path) > CACHE_MAX_AGE:
                    os.remove(path)
            except OSError:
                pass

    def _subtitle_candidates(self, playing_file, language):
        if not playing_file:
            return []
        directory, filename = os.path.split(playing_file.replace("\\", "/"))
        stem = os.path.splitext(filename)[0].lower()
        try:
            _, files = self.xbmcvfs.listdir(directory)
        except Exception:
            return []
        output = []
        language_tokens = {language.lower(), language.lower().split(":", 1)[0]}
        for name in files:
            lower = str(name).lower()
            if not lower.endswith(SUBTITLE_SUFFIXES) or not lower.startswith(stem):
                continue
            extension = os.path.splitext(lower)[1]
            if not any(f".{token}." in lower or lower.endswith(f".{token}{extension}") for token in language_tokens):
                continue
            path = directory.rstrip("/") + "/" + str(name)
            if self.xbmcvfs.exists(path):
                output.append(path)
        return output

    @staticmethod
    def _response_path(response):
        if isinstance(response, dict):
            for key in ("path", "subtitlePath", "subtitle_path"):
                value = response.get(key)
                if isinstance(value, str) and value:
                    return value
            data = response.get("data")
            if isinstance(data, dict):
                return SubtitleService._response_path(data)
        return ""

    def _map_accessible_path(self, path):
        candidates = [path]
        try:
            mapped = self.settings.path_mapper.remote_to_kodi(path)
        except ValueError:
            mapped = ""
        if mapped:
            candidates.insert(0, mapped)
        for candidate in candidates:
            if candidate and self.xbmcvfs.exists(candidate):
                return candidate
        return ""
