# SPDX-License-Identifier: GPL-3.0-or-later
"""Strict, source-aligned Bazarr API boundary."""

from .errors import ApiError
from .http import JsonHttpClient


class BazarrApiError(ApiError):
    """Sanitised Bazarr operation failure without endpoint or credential data."""

    def __init__(self, operation, category, status=None):
        self.operation = str(operation or "request")[:80]
        self.category = str(category or "api")[:40]
        self.status = status if isinstance(status, int) else None
        suffix = f" (HTTP {self.status})" if self.status is not None else ""
        super().__init__(f"Bazarr {self.operation} failed: {self.category}{suffix}", status=self.status)

    def safe_summary(self):
        return {
            "operation": self.operation,
            "category": self.category,
            "status": self.status,
        }


def _flag(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


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


def _category(exc):
    status = getattr(exc, "status", None)
    if status == 401:
        return "authentication"
    if status == 403:
        return "permission"
    if status == 404:
        return "not_found"
    if status in {400, 409, 422}:
        return "validation"
    if isinstance(status, int) and status >= 500:
        return "server"
    text = str(exc).lower()
    if "tls" in text or "certificate" in text:
        return "tls"
    if "timed out" in text or "timeout" in text:
        return "timeout"
    if "connect" in text or "unreachable" in text or "refused" in text:
        return "connection"
    if "json" in text or "response" in text:
        return "malformed_response"
    return "api"


class BazarrClient:
    """Authenticated Bazarr API boundary rooted at /api rather than /api/vN."""

    def __init__(self, base_url, api_key, timeout=15, verify_tls=True,
                 logger=None, user_agent="Kodi-Managarr/unknown"):
        self.http = JsonHttpClient(base_url, api_key, "v1", timeout, verify_tls, logger, user_agent)
        self.http.api_root = f"{self.http.base_url}/api"
        self.last_operation = ""
        self.last_category = ""
        self.last_status = None

    def _request(self, operation, method, path, params=None):
        self.last_operation = operation
        self.last_category = ""
        self.last_status = None
        try:
            response = self.http.request(method, path, params=params)
        except ApiError as exc:
            category = _category(exc)
            self.last_category = category
            self.last_status = getattr(exc, "status", None)
            raise BazarrApiError(operation, category, self.last_status) from exc
        self.last_category = "success"
        return response

    def _contract(self, operation, parser, value, description):
        try:
            return parser(value, description)
        except ApiError as exc:
            self.last_operation = operation
            self.last_category = "unsupported_contract"
            raise BazarrApiError(operation, "unsupported_contract", self.last_status) from exc

    def status(self):
        response = self._contract(
            "status", _object, self._request("status", "GET", "/system/status"), "Bazarr status"
        )
        data = self._contract("status", _object, response.get("data", response), "Bazarr status data")
        version = str(data.get("bazarr_version") or data.get("version") or "").strip()
        if not version:
            self.last_category = "unsupported_contract"
            raise BazarrApiError("status", "unsupported_contract", self.last_status)
        return data

    def languages(self):
        response = self._request("languages", "GET", "/system/languages")
        return self._contract("languages", _records, response, "Bazarr languages")

    def search_movie_subtitles(self, radarr_id):
        response = self._request(
            "movie_search", "GET", "/providers/movies", params={"radarrid": _id(radarr_id, "Movie")}
        )
        return self._contract("movie_search", _records, response, "Movie subtitles")

    def search_episode_subtitles(self, episode_id):
        response = self._request(
            "episode_search", "GET", "/providers/episodes", params={"episodeid": _id(episode_id, "Episode")}
        )
        return self._contract("episode_search", _records, response, "Episode subtitles")

    @staticmethod
    def _download_params(result, language):
        result = _object(result, "Subtitle")
        _, _, qualifier = str(language or "").strip().lower().partition(":")
        provider = str(result.get("provider") or "").strip()
        subtitle = str(result.get("subtitle") or "").strip()
        if not provider or not subtitle:
            raise ApiError("Bazarr subtitle result did not contain provider download identity")
        return {
            "hi": qualifier == "hi" or _flag(result.get("hearing_impaired")) or _flag(result.get("hi")),
            "forced": qualifier == "forced" or _flag(result.get("forced")),
            "original_format": _flag(result.get("original_format")),
            "provider": provider,
            "subtitle": subtitle,
        }

    def download_movie_subtitle(self, radarr_id, language, result):
        params = self._download_params(result, language)
        params["radarrid"] = _id(radarr_id, "Movie")
        return self._request("movie_download", "POST", "/providers/movies", params=params)

    def download_episode_subtitle(self, series_id, episode_id, language, result):
        params = self._download_params(result, language)
        params["seriesid"] = _id(series_id, "Series")
        params["episodeid"] = _id(episode_id, "Episode")
        return self._request("episode_download", "POST", "/providers/episodes", params=params)
