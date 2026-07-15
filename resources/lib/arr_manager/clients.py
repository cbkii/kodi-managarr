from .http import JsonHttpClient


class ServarrClient:
    def __init__(self, base_url, api_key, api_version="v3", timeout=15, verify_tls=True, logger=None):
        self.http = JsonHttpClient(base_url, api_key, api_version, timeout, verify_tls, logger)

    def status(self):
        return self.http.request("GET", "/system/status")

    def command(self, name, **kwargs):
        payload = {"name": name}
        payload.update(kwargs)
        return self.http.request("POST", "/command", payload=payload)

    def mark_history_failed(self, history_id):
        return self.http.request("POST", f"/history/failed/{int(history_id)}", payload={})

    def command_status(self, command_id):
        return self.http.request("GET", f"/command/{int(command_id)}") or {}


class RadarrClient(ServarrClient):
    def all_movies(self):
        return self.http.request("GET", "/movie") or []

    def movie_by_tmdb(self, tmdb_id):
        rows = self.http.request("GET", "/movie", params={"tmdbId": int(tmdb_id)}) or []
        return rows[0] if rows else None

    def movie(self, movie_id):
        return self.http.request("GET", f"/movie/{int(movie_id)}")

    def movie_files(self, movie_id):
        return self.http.request("GET", "/movieFile", params={"movieId": int(movie_id)}) or []

    def delete_movie(self, movie_id, delete_files=True, add_exclusion=True):
        return self.http.request(
            "DELETE",
            f"/movie/{int(movie_id)}",
            params={"deleteFiles": delete_files, "addImportExclusion": add_exclusion},
        )

    def delete_movie_file(self, file_id):
        return self.http.request("DELETE", f"/movieFile/{int(file_id)}")

    def movie_history(self, movie_id, event_type=3):
        return self.http.request(
            "GET", "/history/movie", params={"movieId": int(movie_id), "eventType": event_type}
        ) or []

    def search_movie(self, movie_id):
        return self.command("MoviesSearch", movieIds=[int(movie_id)])

    def rescan_movie(self, movie_id):
        return self.command("RescanMovie", movieId=int(movie_id))


class SonarrClient(ServarrClient):
    def all_series(self):
        return self.http.request("GET", "/series") or []

    def series_by_tvdb(self, tvdb_id):
        rows = self.http.request("GET", "/series", params={"tvdbId": int(tvdb_id)}) or []
        return rows[0] if rows else None

    def series(self, series_id):
        return self.http.request("GET", f"/series/{int(series_id)}")

    def episodes(self, series_id, season_number=None):
        params = {"seriesId": int(series_id)}
        if season_number is not None and season_number >= 0:
            params["seasonNumber"] = int(season_number)
        return self.http.request("GET", "/episode", params=params) or []

    def update_episode(self, episode):
        return self.http.request("PUT", f"/episode/{int(episode['id'])}", payload=episode)

    def episode_files(self, series_id):
        return self.http.request("GET", "/episodeFile", params={"seriesId": int(series_id)}) or []

    def delete_episode_file(self, file_id):
        return self.http.request("DELETE", f"/episodeFile/{int(file_id)}")

    def delete_episode_files(self, file_ids):
        return self.http.request("DELETE", "/episodeFile/bulk", payload={"episodeFileIds": [int(x) for x in file_ids]})

    def delete_series(self, series_id, delete_files=True, add_exclusion=True):
        return self.http.request(
            "DELETE",
            f"/series/{int(series_id)}",
            params={"deleteFiles": delete_files, "addImportListExclusion": add_exclusion},
        )

    def series_history(self, series_id, season_number=None, event_type=3):
        return self.http.request(
            "GET",
            "/history/series",
            params={"seriesId": int(series_id), "seasonNumber": season_number, "eventType": event_type},
        ) or []

    def search_episodes(self, episode_ids):
        return self.command("EpisodeSearch", episodeIds=[int(x) for x in episode_ids])

    def search_series(self, series_id):
        return self.command("SeriesSearch", seriesId=int(series_id))

    def rescan_series(self, series_id):
        return self.command("RescanSeries", seriesId=int(series_id))
