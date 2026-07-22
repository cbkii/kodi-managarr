# SPDX-License-Identifier: GPL-3.0-or-later
import datetime
from .models import RetentionCandidate
from ..kodi_jsonrpc import KodiJsonRpcError
from ..util import normalise_path, as_int
from ..models import SelectedItem
from ..resolver import resolve_movie, resolve_series, resolve_episode_context, ResolutionError

class RetentionEnumerator:
    def __init__(self, kodi_client, arr_manager, path_mapper, logger=None):
        self.kodi = kodi_client
        self.manager = arr_manager
        self.path_mapper = path_mapper
        self.logger = logger

        self.MOVIE_PROPS = ["title", "year", "file", "uniqueid", "playcount", "lastplayed", "dateadded"]
        self.EPISODE_PROPS = ["title", "season", "episode", "file", "tvshowid", "tvshowtitle", "playcount", "lastplayed", "dateadded", "uniqueid"]

        self.PAGE_SIZE = 500

    def get_movies(self, settings):
        if not settings.include_movies:
            return []

        candidates = []
        start = 0
        while True:
            params = {
                "properties": self.MOVIE_PROPS,
                "limits": {"start": start, "end": start + self.PAGE_SIZE}
            }
            try:
                response = self.kodi.call("VideoLibrary.GetMovies", params)
                movies = response.get("movies", [])
            except KodiJsonRpcError as exc:
                if self.logger:
                    self.logger.error("Failed to fetch Kodi movies: %s", exc)
                break

            if not movies:
                break

            for k_movie in movies:
                try:
                    candidate = self._process_kodi_movie(k_movie)
                    if candidate:
                        candidates.append(candidate)
                except Exception as e:
                    if self.logger:
                        self.logger.debug("Skipped movie %s: %s", k_movie.get('movieid'), e)

            start += self.PAGE_SIZE
            if len(movies) < self.PAGE_SIZE:
                break

        return candidates

    def get_episodes(self, settings):
        if not settings.include_episodes:
            return []

        candidates = []
        start = 0
        while True:
            params = {
                "properties": self.EPISODE_PROPS,
                "limits": {"start": start, "end": start + self.PAGE_SIZE}
            }
            try:
                response = self.kodi.call("VideoLibrary.GetEpisodes", params)
                episodes = response.get("episodes", [])
            except KodiJsonRpcError as exc:
                if self.logger:
                    self.logger.error("Failed to fetch Kodi episodes: %s", exc)
                break

            if not episodes:
                break

            # Note: Kodi VideoLibrary.GetEpisodes without tvshowid fetches all episodes globally
            for k_episode in episodes:
                try:
                    candidate = self._process_kodi_episode(k_episode)
                    if candidate:
                        candidates.append(candidate)
                except Exception as e:
                    if self.logger:
                        self.logger.debug("Skipped episode %s: %s", k_episode.get('episodeid'), e)

            start += self.PAGE_SIZE
            if len(episodes) < self.PAGE_SIZE:
                break

        return candidates

    def _parse_kodi_date(self, date_str):
        if not date_str:
            return None
        try:
            dt = datetime.datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
            return dt.replace(tzinfo=datetime.timezone.utc).timestamp()
        except ValueError:
            return None

    def _parse_arr_date(self, date_str):
        if not date_str:
            return None
        # Servarr uses ISO 8601 like: 2023-01-01T12:00:00Z
        try:
            dt = datetime.datetime.strptime(date_str.split('.')[0].replace('Z', ''), "%Y-%m-%dT%H:%M:%S")
            return dt.replace(tzinfo=datetime.timezone.utc).timestamp()
        except ValueError:
            return None

    def _get_conservative_added_timestamp(self, ts_list):
        valid_ts = [ts for ts in ts_list if ts is not None and ts > 0]
        if not valid_ts:
            return None
        return max(valid_ts)

    def _process_kodi_movie(self, k_movie):
        db_id = as_int(k_movie.get("movieid"))
        if db_id <= 0:
            return None

        selected = SelectedItem(
            media_type="movie",
            db_id=db_id,
            title=k_movie.get("title", ""),
            year=as_int(k_movie.get("year")),
            file_path=k_movie.get("file", ""),
            unique_ids=k_movie.get("uniqueid", {})
        )

        try:
            arr_movie = resolve_movie(selected, self.manager.radarr, self.path_mapper)
        except ResolutionError:
            return None

        if not arr_movie.get("hasFile"):
            return None

        # Get Radarr movie file
        try:
            files = self.manager.radarr.movie_files(arr_movie["id"])
            if not files:
                return None
            arr_file = files[0]
        except Exception:
            return None

        kodi_added = self._parse_kodi_date(k_movie.get("dateadded"))
        arr_added = self._parse_arr_date(arr_movie.get("added"))
        arr_file_added = self._parse_arr_date(arr_file.get("dateAdded"))

        conservative_added = self._get_conservative_added_timestamp([kodi_added, arr_added, arr_file_added])

        playcount = as_int(k_movie.get("playcount"))
        watched = playcount > 0
        last_played = self._parse_kodi_date(k_movie.get("lastplayed")) if watched else None

        return RetentionCandidate(
            media_type="movie",
            db_id=db_id,
            arr_id=arr_movie["id"],
            file_id=as_int(arr_file.get("id")),
            title=k_movie.get("title", ""),
            display_name=selected.display_name,
            watched=watched,
            last_played=last_played,
            date_added=conservative_added,
            unique_ids=selected.unique_ids
        )

    def _process_kodi_episode(self, k_episode):
        db_id = as_int(k_episode.get("episodeid"))
        if db_id <= 0:
            return None

        selected = SelectedItem(
            media_type="episode",
            db_id=db_id,
            title=k_episode.get("title", ""),
            tvshow_title=k_episode.get("tvshowtitle", ""),
            tvshow_db_id=as_int(k_episode.get("tvshowid")),
            season=as_int(k_episode.get("season")),
            episode=as_int(k_episode.get("episode")),
            file_path=k_episode.get("file", ""),
            unique_ids=k_episode.get("uniqueid", {})
        )

        # We need the series context for Sonarr resolution
        try:
            series = resolve_series(selected, self.manager.sonarr, self.path_mapper)
            _, linked, file_record = resolve_episode_context(selected, self.manager.sonarr, series)
        except ResolutionError:
            return None

        if not file_record:
            return None

        # Check if season zero (specials) is excluded or handled differently if needed by settings, but we include it by default

        kodi_added = self._parse_kodi_date(k_episode.get("dateadded"))
        arr_file_added = self._parse_arr_date(file_record.get("dateAdded"))

        conservative_added = self._get_conservative_added_timestamp([kodi_added, arr_file_added])

        playcount = as_int(k_episode.get("playcount"))
        watched = playcount > 0
        last_played = self._parse_kodi_date(k_episode.get("lastplayed")) if watched else None

        return RetentionCandidate(
            media_type="episode",
            db_id=db_id,
            arr_id=series["id"], # Store series ID as arr_id for episodes to group/identify them
            file_id=as_int(file_record.get("id")),
            title=k_episode.get("title", ""),
            display_name=selected.display_name,
            watched=watched,
            last_played=last_played,
            date_added=conservative_added,
            unique_ids=selected.unique_ids,
            season=selected.season,
            episode=selected.episode,
            file_path=selected.file_path
        )
