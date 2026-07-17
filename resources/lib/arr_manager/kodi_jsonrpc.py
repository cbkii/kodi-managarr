# SPDX-License-Identifier: GPL-3.0-or-later
import json


class KodiJsonRpcError(Exception):
    pass


class KodiJsonRpcClient:
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
        return self._detail(self.call("VideoLibrary.GetMovieDetails", {"movieid": int(movie_id), "properties": self.MOVIE_PROPERTIES}), "moviedetails")

    def movies(self):
        return self._items(self.call("VideoLibrary.GetMovies", {"properties": self.MOVIE_PROPERTIES}), "movies")

    def tvshow_details(self, tvshow_id):
        return self._detail(self.call("VideoLibrary.GetTVShowDetails", {"tvshowid": int(tvshow_id), "properties": self.TVSHOW_PROPERTIES}), "tvshowdetails")

    def tvshows(self):
        return self._items(self.call("VideoLibrary.GetTVShows", {"properties": self.TVSHOW_PROPERTIES}), "tvshows")

    def episode_details(self, episode_id):
        return self._detail(self.call("VideoLibrary.GetEpisodeDetails", {"episodeid": int(episode_id), "properties": self.EPISODE_PROPERTIES}), "episodedetails")

    def episodes(self, tvshow_id):
        if int(tvshow_id or 0) <= 0:
            raise KodiJsonRpcError("A validated Kodi TV show ID is required for targeted episode cleanup")
        return self._items(self.call("VideoLibrary.GetEpisodes", {"tvshowid": int(tvshow_id), "properties": self.EPISODE_PROPERTIES}), "episodes")

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
