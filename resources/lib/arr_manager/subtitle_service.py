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
from .kodi_jsonrpc import KodiJsonRpcError
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


def _score(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _display_text(value, limit=120):
    text = " ".join(str(value or "").split())
    if "://" in text:
        return ""
    return text[:limit]


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


def _language_parts(value):
    text = str(value or "").strip().lower()
    base, separator, qualifier = text.partition(":")
    return base, qualifier if separator else ""


def _language_matches(configured, variant):
    configured_base, configured_qualifier = _language_parts(configured)
    variant_base, variant_qualifier = _language_parts(variant)
    if not configured_base or configured_base != variant_base:
        return False
    return not configured_qualifier or configured_qualifier == variant_qualifier


def _language_allowed(variant, allowed_languages):
    return any(_language_matches(configured, variant) for configured in allowed_languages)


def _release_match(row):
    value = row.get("release_info") or row.get("matches") or ""
    if isinstance(value, (list, tuple, set)):
        value = ", ".join(str(item) for item in value if item)
    elif isinstance(value, dict):
        value = ", ".join(str(key) for key, matched in value.items() if matched)
    return _display_text(value)


def _result_label(addon, row, language):
    flags = []
    if row.get("forced"):
        flags.append(imessage(addon, "subtitle_forced"))
    if row.get("hearing_impaired") or row.get("hi"):
        flags.append(imessage(addon, "subtitle_hi"))
    suffix = imessage(addon, "subtitle_flags", flags=", ".join(flags)) if flags else ""

    provider = _display_text(row.get("provider"), 80) or imessage(addon, "subtitle_best_match")
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


def _opaque_identity(value, description):
    text = str(value or "").strip()
    if not text or len(text) > 4096 or "\r" in text or "\n" in text or "://" in text:
        raise SafetyError(f"Bazarr {description} is missing or unsafe")
    return text


def _safe_result(row):
    return {
        "provider": _opaque_identity(row.get("provider"), "provider identity"),
        "subtitle": _opaque_identity(row.get("subtitle"), "subtitle identity"),
        "original_format": bool(row.get("original_format")),
        "forced": bool(row.get("forced")),
        "hearing_impaired": bool(row.get("hearing_impaired")),
        "hi": bool(row.get("hi")),
    }


def _select_results(rows, allowed_languages):
    allowed = []
    for value in allowed_languages:
        normalised = str(value or "").strip().lower()
        if normalised and normalised not in allowed:
            allowed.append(normalised)
    best = {}
    priority = {}
    for row in rows:
        variant = _language_key(row)
        matching = [index for index, configured in enumerate(allowed) if _language_matches(configured, variant)]
        if not matching:
            continue
        priority[variant] = min(priority.get(variant, matching[0]), matching[0])
        score = _score(row.get("score"))
        if variant not in best or score > best[variant][0]:
            best[variant] = (score, row)
    qualifier_order = {"": 0, "forced": 1, "hi": 2}
    return [
        (variant, best[variant][1])
        for variant in sorted(
            best,
            key=lambda value: (priority[value], qualifier_order.get(_language_parts(value)[1], 9), value),
        )
    ]


def selected_from_player(addon, xbmc_module, kodi_client):
    db_type = str(xbmc_module.getInfoLabel("VideoPlayer.DBTYPE") or "").strip().lower()
    db_id = _positive_int(xbmc_module.getInfoLabel("VideoPlayer.DBID"), 0)
    playing_file = str(xbmc_module.Player().getPlayingFile() or "")
    if db_type == "movie" and db_id > 0:
        detail = kodi_client.movie_details(db_id)
        return SelectedItem(
            media_type="movie", db_id=db_id, title=str(detail.get("title") or ""),
            year=_positive_int(detail.get("year"), 0), file_path=str(detail.get("file") or playing_file),
            unique_ids=dict(detail.get("uniqueid") or {}),
        )
    if db_type == "episode" and db_id > 0:
        detail = kodi_client.episode_details(db_id)
        tvshow_id = _positive_int(detail.get("tvshowid"), 0)
        series_detail = {}
        if tvshow_id > 0:
            try:
                series_detail = kodi_client.tvshow_details(tvshow_id)
            except KodiJsonRpcError:
                series_detail = {}
        return SelectedItem(
            media_type="episode", db_id=db_id, title=str(detail.get("title") or ""),
            tvshow_title=str(detail.get("tvshowtitle") or series_detail.get("title") or ""),
            tvshow_db_id=tvshow_id,
            season=_positive_int(detail.get("season"), -1), episode=_positive_int(detail.get("episode"), -1),
            file_path=str(detail.get("file") or playing_file), unique_ids=dict(detail.get("uniqueid") or {}),
            series_year=_positive_int(series_detail.get("year"), 0),
            series_unique_ids=dict(series_detail.get("uniqueid") or {}),
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
            target = {"media_type": "movie", "kodi_db_id": int(selected.db_id), "radarr_id": int(movie["id"])}
            rows = self.manager.bazarr.search_movie_subtitles(movie["id"])
        else:
            series = resolve_series(selected, self.manager.sonarr, self.settings.path_mapper)
            episode = resolve_episode(selected, self.manager.sonarr, series)
            target = {
                "media_type": "episode", "kodi_db_id": int(selected.db_id),
                "series_id": int(series["id"]), "episode_id": int(episode["id"]),
            }
            rows = self.manager.bazarr.search_episode_subtitles(episode["id"])

        output = []
        for language, row in _select_results(rows, self.settings.bazarr_languages):
            try:
                safe_result = _safe_result(row)
            except SafetyError:
                if self.logger:
                    self.logger.warning("Skipped malformed Bazarr subtitle result")
                continue
            payload = dict(target)
            payload.update({"language": language, "result": safe_result, "created": int(time.time())})
            token = self._save_cache(payload)
            label, label2 = _result_label(self.addon, row, language)
            output.append({
                "label": label,
                "label2": label2,
                "url": f"{base_url}?{urlencode({'action': 'download', 'token': token})}",
            })
        return output

    def download(self, token):
        payload = self._consume_cache(token)
        language = str(payload.get("language") or "").lower()
        if not _language_allowed(language, self.settings.bazarr_languages):
            raise SafetyError(imessage(self.addon, "subtitle_invalid_request"))
        media_type, kodi_db_id, playing_file = self._current_playback()
        if media_type != payload.get("media_type") or kodi_db_id != _positive_int(payload.get("kodi_db_id"), 0):
            raise SafetyError(imessage(self.addon, "subtitle_invalid_request"))
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
                return mapped
        deadline = time.monotonic() + 15
        last_candidates = before
        while time.monotonic() < deadline:
            candidates = set(self._subtitle_candidates(playing_file, language))
            last_candidates = candidates
            preferred = sorted(candidates - before) or sorted(candidates)
            if preferred:
                return preferred[-1]
            if self.ui.wait_for_abort(0.5):
                break
        if last_candidates:
            return sorted(last_candidates)[-1]
        raise SafetyError(imessage(self.addon, "subtitle_not_found"))

    def _current_playback(self):
        import xbmc
        media_type = str(xbmc.getInfoLabel("VideoPlayer.DBTYPE") or "").strip().lower()
        db_id = _positive_int(xbmc.getInfoLabel("VideoPlayer.DBID"), 0)
        playing_file = str(xbmc.Player().getPlayingFile() or "")
        if media_type not in {"movie", "episode"} or db_id <= 0 or not playing_file:
            raise SafetyError(imessage(self.addon, "subtitle_playback_changed"))
        return media_type, db_id, playing_file

    def _save_cache(self, payload):
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
        token = hashlib.sha256(raw + os.urandom(16)).hexdigest()[:32]
        path = os.path.join(self.profile, f"subtitle-{token}.json")
        temporary = path + ".tmp"
        with open(temporary, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, sort_keys=True, separators=(",", ":"))
        try:
            os.chmod(temporary, 0o600)
        except OSError:
            pass
        os.replace(temporary, path)
        self._prune_cache()
        return token

    def _cache_path(self, token):
        if not CACHE_TOKEN_RE.fullmatch(str(token or "")):
            raise SafetyError(imessage(self.addon, "subtitle_invalid_request"))
        return os.path.join(self.profile, f"subtitle-{token}.json")

    def _validate_cache_payload(self, payload):
        if not isinstance(payload, dict):
            raise SafetyError(imessage(self.addon, "subtitle_invalid_request"))
        created = _positive_int(payload.get("created"), 0)
        age = int(time.time()) - created
        media_type = payload.get("media_type")
        language = str(payload.get("language") or "").strip().lower()
        if created <= 0 or age < -60 or age > CACHE_MAX_AGE or media_type not in {"movie", "episode"}:
            raise SafetyError(imessage(self.addon, "subtitle_invalid_request"))
        if _positive_int(payload.get("kodi_db_id"), 0) <= 0 or not _language_parts(language)[0]:
            raise SafetyError(imessage(self.addon, "subtitle_invalid_request"))
        if media_type == "movie":
            if _positive_int(payload.get("radarr_id"), 0) <= 0:
                raise SafetyError(imessage(self.addon, "subtitle_invalid_request"))
        elif _positive_int(payload.get("series_id"), 0) <= 0 or _positive_int(payload.get("episode_id"), 0) <= 0:
            raise SafetyError(imessage(self.addon, "subtitle_invalid_request"))
        result = payload.get("result")
        if not isinstance(result, dict) or _safe_result(result) != result:
            raise SafetyError(imessage(self.addon, "subtitle_invalid_request"))
        return payload

    def _read_cache_path(self, path):
        try:
            if time.time() - os.path.getmtime(path) > CACHE_MAX_AGE:
                raise SafetyError(imessage(self.addon, "subtitle_invalid_request"))
            with open(path, encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, ValueError) as exc:
            raise SafetyError(imessage(self.addon, "subtitle_invalid_request")) from exc
        return self._validate_cache_payload(payload)

    def _load_cache(self, token):
        return self._read_cache_path(self._cache_path(token))

    def _consume_cache(self, token):
        path = self._cache_path(token)
        claimed = path + ".claimed"
        try:
            os.replace(path, claimed)
        except OSError as exc:
            raise SafetyError(imessage(self.addon, "subtitle_invalid_request")) from exc
        try:
            return self._read_cache_path(claimed)
        finally:
            try:
                os.remove(claimed)
            except OSError:
                pass

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
