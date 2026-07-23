# SPDX-License-Identifier: GPL-3.0-or-later
from .errors import ApiError
from .http import JsonHttpClient


def _object(value, description):
    if not isinstance(value, dict):
        raise ApiError(f"{description} response was not an object")
    return value


def _list(value, description):
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ApiError(f"{description} response was not a list of objects")
    return value


def _records(value, description):
    if isinstance(value, list):
        return _list(value, description)
    obj = _object(value, description)
    for key in ("data", "records", "results"):
        if key in obj:
            return _list(obj[key], description)
    raise ApiError(f"{description} response did not contain records")


def _id(value, description):
    if isinstance(value, bool):
        raise ApiError(f"{description} did not contain a valid ID")
    if isinstance(value, int):
        result = value
    elif isinstance(value, str) and value.strip().isdigit():
        result = int(value.strip())
    else:
        raise ApiError(f"{description} did not contain a valid ID")
    if result <= 0:
        raise ApiError(f"{description} did not contain a valid ID")
    return result


class ServarrClient:
    def __init__(self, base_url, api_key, api_version="v3", timeout=15, verify_tls=True,
                 logger=None, user_agent="Kodi-Managarr/unknown"):
        self.http = JsonHttpClient(base_url, api_key, api_version, timeout, verify_tls, logger, user_agent)

    def status(self):
        return _object(self.http.request("GET", "/system/status"), "System status")

    def command(self, name, **kwargs):
        payload = {"name": name}
        payload.update(kwargs)
        response = _object(self.http.request("POST", "/command", payload=payload), "Command")
        _id(response.get("id"), "Command")
        return response

    def mark_history_failed(self, history_id):
        return self.http.request("POST", f"/history/failed/{_id(history_id, 'History')}", payload={})

    def command_status(self, command_id):
        return _object(self.http.request("GET", f"/command/{_id(command_id, 'Command')}"), "Command status")

    def quality_profiles(self):
        return _list(self.http.request("GET", "/qualityprofile"), "Quality profiles")

    def health(self):
        return _list(self.http.request("GET", "/health"), "Health")

    def root_folders(self):
        return _list(self.http.request("GET", "/rootfolder"), "Root folders")

    def queue_overview(self):
        return _object(self.http.request("GET", "/queue", params={"page": 1, "pageSize": 20}), "Queue")

    def remove_queue_item(self, queue_id, remove_from_client=True, blocklist=False):
        return self.http.request(
            "DELETE", f"/queue/{_id(queue_id, 'Queue item')}",
            params={"removeFromClient": remove_from_client, "blocklist": blocklist},
        )

    @staticmethod
    def _queue_records(response):
        obj = _object(response, "Queue")
        return _list(obj.get("records"), "Queue records")


class RadarrClient(ServarrClient):
    def lookup_movie(self, term):
        return _list(self.http.request("GET", "/movie/lookup", params={"term": term}), "Movie lookup")

    def add_movie(self, movie):
        return _object(self.http.request("POST", "/movie", payload=_object(dict(movie), "Movie add")), "Movie add")

    def releases(self, movie_id):
        return _list(self.http.request("GET", "/release", params={"movieId": _id(movie_id, "Movie")}), "Releases")

    def download_release(self, release):
        return _object(self.http.request("POST", "/release", payload=_object(dict(release), "Release")), "Release download")

    def wanted_missing(self):
        return _object(self.http.request("GET", "/wanted/missing", params={"page": 1, "pageSize": 1}), "Wanted movies")

    def all_movies(self):
        return _list(self.http.request("GET", "/movie"), "Movies")

    def movie_by_tmdb(self, tmdb_id):
        rows = _list(self.http.request("GET", "/movie", params={"tmdbId": int(tmdb_id)}), "Movie lookup")
        if len(rows) > 1:
            raise ApiError("Radarr returned multiple movies for the same TMDb ID")
        return rows[0] if rows else None

    def movie(self, movie_id):
        return _object(self.http.request("GET", f"/movie/{_id(movie_id, 'Movie')}"), "Movie")

    def update_movie(self, movie):
        movie = _object(dict(movie), "Movie update")
        return _object(self.http.request("PUT", f"/movie/{_id(movie.get('id'), 'Movie')}", payload=movie), "Movie update")

    def movie_files(self, movie_id):
        return _list(self.http.request("GET", "/movieFile", params={"movieId": _id(movie_id, "Movie")}), "Movie files")

    def delete_movie(self, movie_id, delete_files=True, add_exclusion=True):
        return self.http.request("DELETE", f"/movie/{_id(movie_id, 'Movie')}",
                                 params={"deleteFiles": delete_files, "addImportExclusion": add_exclusion})

    def delete_movie_file(self, file_id):
        return self.http.request("DELETE", f"/movieFile/{_id(file_id, 'Movie file')}")

    def movie_history(self, movie_id, event_type=3):
        return _list(self.http.request("GET", "/history/movie",
                                       params={"movieId": _id(movie_id, "Movie"), "eventType": event_type}), "Movie history")

    def queue(self, movie_id):
        return self._queue_records(self.http.request("GET", "/queue", params={
            "page": 1, "pageSize": 100, "includeMovie": True, "movieIds": [_id(movie_id, "Movie")],
        }))

    def search_movie(self, movie_id):
        return self.command("MoviesSearch", movieIds=[_id(movie_id, "Movie")])

    def rescan_movie(self, movie_id):
        return self.command("RescanMovie", movieId=_id(movie_id, "Movie"))


class SonarrClient(ServarrClient):
    def lookup_series(self, term):
        return _list(self.http.request("GET", "/series/lookup", params={"term": term}), "Series lookup")

    def add_series(self, series):
        return _object(self.http.request("POST", "/series", payload=_object(dict(series), "Series add")), "Series add")

    def releases(self, episode_id):
        return _list(self.http.request("GET", "/release", params={"episodeId": _id(episode_id, "Episode")}), "Releases")

    def download_release(self, release):
        return _object(self.http.request("POST", "/release", payload=_object(dict(release), "Release")), "Release download")

    def wanted_missing(self):
        return _object(self.http.request("GET", "/wanted/missing", params={"page": 1, "pageSize": 1}), "Wanted episodes")

    def all_series(self):
        return _list(self.http.request("GET", "/series"), "Series")

    def series_by_tvdb(self, tvdb_id):
        rows = _list(self.http.request("GET", "/series", params={"tvdbId": int(tvdb_id)}), "Series lookup")
        if len(rows) > 1:
            raise ApiError("Sonarr returned multiple series for the same TVDb ID")
        return rows[0] if rows else None

    def series(self, series_id):
        return _object(self.http.request("GET", f"/series/{_id(series_id, 'Series')}"), "Series")

    def update_series(self, series):
        series = _object(dict(series), "Series update")
        return _object(self.http.request("PUT", f"/series/{_id(series.get('id'), 'Series')}", payload=series), "Series update")

    def episodes(self, series_id, season_number=None):
        params = {"seriesId": _id(series_id, "Series")}
        if season_number is not None and int(season_number) >= 0:
            params["seasonNumber"] = int(season_number)
        return _list(self.http.request("GET", "/episode", params=params), "Episodes")

    def update_episode(self, episode):
        episode = _object(dict(episode), "Episode update")
        return _object(self.http.request("PUT", f"/episode/{_id(episode.get('id'), 'Episode')}", payload=episode), "Episode update")

    def set_episodes_monitored(self, episode_ids, monitored):
        valid_ids = []
        seen = set()
        for value in episode_ids:
            episode_id = _id(value, "Episode")
            if episode_id not in seen:
                seen.add(episode_id)
                valid_ids.append(episode_id)
        if not valid_ids:
            return None
        return self.http.request("PUT", "/episode/monitor", payload={"episodeIds": valid_ids, "monitored": bool(monitored)})

    def episode_files(self, series_id):
        return _list(self.http.request("GET", "/episodeFile", params={"seriesId": _id(series_id, "Series")}), "Episode files")

    def delete_episode_file(self, file_id):
        return self.http.request("DELETE", f"/episodeFile/{_id(file_id, 'Episode file')}")

    def delete_episode_files(self, file_ids):
        ids = [_id(value, "Episode file") for value in file_ids]
        return self.http.request("DELETE", "/episodeFile/bulk", payload={"episodeFileIds": ids})

    def delete_series(self, series_id, delete_files=True, add_exclusion=True):
        return self.http.request("DELETE", f"/series/{_id(series_id, 'Series')}",
                                 params={"deleteFiles": delete_files, "addImportListExclusion": add_exclusion})

    def series_history(self, series_id, season_number=None, event_type=3):
        return _list(self.http.request("GET", "/history/series", params={
            "seriesId": _id(series_id, "Series"), "seasonNumber": season_number, "eventType": event_type,
        }), "Series history")

    def queue(self, series_id):
        return self._queue_records(self.http.request("GET", "/queue", params={
            "page": 1, "pageSize": 100, "includeSeries": True, "includeEpisode": True,
            "seriesIds": [_id(series_id, "Series")],
        }))

    def search_episodes(self, episode_ids):
        return self.command("EpisodeSearch", episodeIds=[_id(value, "Episode") for value in episode_ids])

    def search_series(self, series_id):
        return self.command("SeriesSearch", seriesId=_id(series_id, "Series"))

    def rescan_series(self, series_id):
        return self.command("RescanSeries", seriesId=_id(series_id, "Series"))


class ProwlarrClient:
    """Narrow Prowlarr v1 boundary; it never exposes media-management methods."""

    def __init__(self, base_url, api_key, api_version="v1", timeout=15, verify_tls=True,
                 logger=None, user_agent="Kodi-Managarr/unknown"):
        self.http = JsonHttpClient(base_url, api_key, api_version, timeout, verify_tls, logger, user_agent)

    def status(self):
        return _object(self.http.request("GET", "/system/status"), "Prowlarr status")

    def health(self):
        return _list(self.http.request("GET", "/health"), "Prowlarr health")

    def indexers(self):
        return _list(self.http.request("GET", "/indexer"), "Prowlarr indexers")

    def search(self, query):
        return _records(self.http.request("GET", "/search", params={"query": str(query or "")}), "Prowlarr search")


class BazarrClient:
    """Bazarr's authenticated API is rooted at /api rather than /api/vN."""

    def __init__(self, base_url, api_key, timeout=15, verify_tls=True,
                 logger=None, user_agent="Kodi-Managarr/unknown"):
        self.http = JsonHttpClient(base_url, api_key, "v1", timeout, verify_tls, logger, user_agent)
        self.http.api_root = f"{self.http.base_url}/api"

    def status(self):
        return _object(self.http.request("GET", "/system/status"), "Bazarr status")

    def languages(self):
        return _records(self.http.request("GET", "/system/languages"), "Bazarr languages")

    def search_movie_subtitles(self, radarr_id):
        return _records(self.http.request("GET", "/providers/movies",
                                          params={"radarrid": _id(radarr_id, "Movie")}), "Movie subtitles")

    def search_episode_subtitles(self, episode_id):
        return _records(self.http.request("GET", "/providers/episodes",
                                          params={"episodeid": _id(episode_id, "Episode")}), "Episode subtitles")

    @staticmethod
    def _download_params(result, language):
        result = _object(result, "Subtitle")
        raw_language = str(language or "").strip().lower()
        base_language, _, qualifier = raw_language.partition(":")
        params = {
            "language": base_language,
            "forced": qualifier == "forced" or bool(result.get("forced")),
            "hi": qualifier == "hi" or bool(result.get("hearing_impaired") or result.get("hi")),
        }
        if not params["language"]:
            raise ApiError("Subtitle result did not contain a language")
        return params

    def download_movie_subtitle(self, radarr_id, language, result):
        params = self._download_params(result, language)
        params["radarrid"] = _id(radarr_id, "Movie")
        return self.http.request("PATCH", "/movies/subtitles", params=params)

    def download_episode_subtitle(self, series_id, episode_id, language, result):
        params = self._download_params(result, language)
        params["seriesid"] = _id(series_id, "Series")
        params["episodeid"] = _id(episode_id, "Episode")
        return self.http.request("PATCH", "/episodes/subtitles", params=params)
