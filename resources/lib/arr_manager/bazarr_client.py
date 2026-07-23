# SPDX-License-Identifier: GPL-3.0-or-later
from .errors import ApiError
from .http import JsonHttpClient


def _object(value, description):
    if not isinstance(value, dict):
        raise ApiError(f"{description} response was not an object")
    return value


def _records(value, description):
    if isinstance(value, list):
        rows = value
    elif isinstance(value, dict):
        rows = next((value[key] for key in ("data", "records", "results") if key in value), None)
    else:
        rows = None
    if not isinstance(rows, list) or any(not isinstance(item, dict) for item in rows):
        raise ApiError(f"{description} response did not contain a list of objects")
    return rows


def _id(value, description):
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ApiError(f"{description} did not contain a valid ID") from exc
    if result <= 0:
        raise ApiError(f"{description} did not contain a valid ID")
    return result


class BazarrClient:
    """Authenticated Bazarr API boundary rooted at /api rather than /api/vN."""

    def __init__(self, base_url, api_key, timeout=15, verify_tls=True,
                 logger=None, user_agent="Kodi-Managarr/unknown"):
        self.http = JsonHttpClient(base_url, api_key, "v1", timeout, verify_tls, logger, user_agent)
        self.http.api_root = f"{self.http.base_url}/api"

    def status(self):
        return _object(self.http.request("GET", "/system/status"), "Bazarr status")

    def languages(self):
        return _records(self.http.request("GET", "/system/languages"), "Bazarr languages")

    def search_movie_subtitles(self, radarr_id):
        return _records(
            self.http.request("GET", "/providers/movies", params={"radarrid": _id(radarr_id, "Movie")}),
            "Movie subtitles",
        )

    def search_episode_subtitles(self, episode_id):
        return _records(
            self.http.request("GET", "/providers/episodes", params={"episodeid": _id(episode_id, "Episode")}),
            "Episode subtitles",
        )

    @staticmethod
    def _download_params(result, language):
        result = _object(result, "Subtitle")
        _, _, qualifier = str(language or "").strip().lower().partition(":")
        provider = str(result.get("provider") or "").strip()
        subtitle = str(result.get("subtitle") or "").strip()
        if not provider or not subtitle:
            raise ApiError("Bazarr subtitle result did not contain provider download identity")
        return {
            "hi": qualifier == "hi" or bool(result.get("hearing_impaired") or result.get("hi")),
            "forced": qualifier == "forced" or bool(result.get("forced")),
            "original_format": bool(result.get("original_format")),
            "provider": provider,
            "subtitle": subtitle,
        }

    def download_movie_subtitle(self, radarr_id, language, result):
        params = self._download_params(result, language)
        params["radarrid"] = _id(radarr_id, "Movie")
        return self.http.request("POST", "/providers/movies", params=params)

    def download_episode_subtitle(self, series_id, episode_id, language, result):
        params = self._download_params(result, language)
        params["seriesid"] = _id(series_id, "Series")
        params["episodeid"] = _id(episode_id, "Episode")
        return self.http.request("POST", "/providers/episodes", params=params)
