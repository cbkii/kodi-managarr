# SPDX-License-Identifier: GPL-3.0-or-later
import datetime

from ..errors import ResolutionError, SafetyError
from ..models import SelectedItem
from ..resolver import resolve_episode_context, resolve_movie, resolve_series
from ..util import as_int
from .models import RetentionCandidate


class RetentionEnumerator:
    MOVIE_PROPS = ["title", "year", "file", "uniqueid", "playcount", "lastplayed", "dateadded", "rating"]
    EPISODE_PROPS = [
        "title", "season", "episode", "file", "tvshowid", "tvshowtitle",
        "playcount", "lastplayed", "dateadded", "uniqueid",
    ]
    TVSHOW_PROPS = ["title", "year", "uniqueid"]
    PAGE_SIZE = 500

    def __init__(self, kodi_client, arr_manager, path_mapper, logger=None):
        self.kodi = kodi_client
        self.manager = arr_manager
        self.path_mapper = path_mapper
        self.logger = logger
        self._series_cache = {}

    def get_candidates(self, settings):
        return self.get_movies(settings) + self.get_episodes(settings)

    def get_movies(self, settings):
        if not settings.include_movies:
            return []
        return self._paged("VideoLibrary.GetMovies", "movies", self.MOVIE_PROPS, self._process_kodi_movie)

    def get_episodes(self, settings):
        if not settings.include_episodes:
            return []
        return self._paged("VideoLibrary.GetEpisodes", "episodes", self.EPISODE_PROPS, self._process_kodi_episode)

    def _paged(self, method, key, properties, processor):
        candidates = []
        start = 0
        while True:
            try:
                response = self.kodi.call(method, {
                    "properties": properties,
                    "limits": {"start": start, "end": start + self.PAGE_SIZE},
                })
            except Exception as exc:
                raise SafetyError(f"Kodi library enumeration failed before retention could run: {exc}") from exc
            rows = response.get(key, []) if isinstance(response, dict) else []
            if not isinstance(rows, list) or any(not isinstance(item, dict) for item in rows):
                raise SafetyError(f"Kodi returned malformed {key} during retention enumeration")
            if not rows:
                break
            for row in rows:
                try:
                    candidate = processor(row)
                except ResolutionError as exc:
                    if self.logger:
                        self.logger.debug("Retention skipped unresolved Kodi item %s: %s", row.get("label") or row.get("title"), exc)
                    continue
                except Exception as exc:
                    if self.logger:
                        self.logger.warning("Retention skipped malformed Kodi item %s: %s", row.get("label") or row.get("title"), exc)
                    continue
                if candidate:
                    candidates.append(candidate)
            start += self.PAGE_SIZE
            if len(rows) < self.PAGE_SIZE:
                break
        return candidates

    @staticmethod
    def _parse_kodi_date(value):
        if not value:
            return None
        try:
            parsed = datetime.datetime.strptime(str(value), "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None
        return parsed.replace(tzinfo=datetime.timezone.utc).timestamp()

    @staticmethod
    def _parse_arr_date(value):
        if not value:
            return None
        text = str(value).strip().replace("Z", "+00:00")
        try:
            parsed = datetime.datetime.fromisoformat(text)
        except ValueError:
            try:
                parsed = datetime.datetime.strptime(text.split(".", 1)[0], "%Y-%m-%dT%H:%M:%S")
            except ValueError:
                return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=datetime.timezone.utc)
        return parsed.timestamp()

    @staticmethod
    def _conservative_added(*timestamps):
        valid = [value for value in timestamps if value is not None and value > 0]
        return max(valid) if valid else None

    @staticmethod
    def _rating(value):
        try:
            result = float(value)
        except (TypeError, ValueError):
            return None
        return result if 0 < result <= 10 else None

    def _process_kodi_movie(self, row):
        db_id = as_int(row.get("movieid"))
        if db_id <= 0:
            return None
        selected = SelectedItem(
            media_type="movie",
            db_id=db_id,
            title=row.get("title", ""),
            year=as_int(row.get("year")),
            file_path=row.get("file", ""),
            unique_ids=row.get("uniqueid") or {},
        )
        movie = resolve_movie(selected, self.manager.radarr, self.path_mapper)
        if not movie.get("hasFile"):
            return None
        files = self.manager.radarr.movie_files(movie["id"])
        if len(files) != 1:
            raise ResolutionError(f"Expected one Radarr movie file for {selected.display_name}; found {len(files)}")
        file_record = files[0]
        watched = as_int(row.get("playcount")) > 0
        return RetentionCandidate(
            media_type="movie",
            db_id=db_id,
            arr_id=int(movie["id"]),
            file_id=as_int(file_record.get("id")) or None,
            title=row.get("title", ""),
            display_name=selected.display_name,
            watched=watched,
            last_played=self._parse_kodi_date(row.get("lastplayed")) if watched else None,
            date_added=self._conservative_added(
                self._parse_kodi_date(row.get("dateadded")),
                self._parse_arr_date(movie.get("added")),
                self._parse_arr_date(file_record.get("dateAdded")),
            ),
            unique_ids=selected.unique_ids,
            file_path=selected.file_path,
            rating=self._rating(row.get("rating")),
        )

    def _series_identity(self, tvshow_id):
        if tvshow_id in self._series_cache:
            return self._series_cache[tvshow_id]
        result = self.kodi.call("VideoLibrary.GetTVShowDetails", {
            "tvshowid": int(tvshow_id),
            "properties": self.TVSHOW_PROPS,
        })
        details = result.get("tvshowdetails") if isinstance(result, dict) else None
        if not isinstance(details, dict):
            raise SafetyError("Kodi returned malformed TV show details during retention enumeration")
        identity = {
            "title": details.get("title", ""),
            "year": as_int(details.get("year")),
            "uniqueid": details.get("uniqueid") or {},
        }
        self._series_cache[tvshow_id] = identity
        return identity

    def _process_kodi_episode(self, row):
        db_id = as_int(row.get("episodeid"))
        tvshow_id = as_int(row.get("tvshowid"))
        if db_id <= 0 or tvshow_id <= 0:
            return None
        series_identity = self._series_identity(tvshow_id)
        selected = SelectedItem(
            media_type="episode",
            db_id=db_id,
            title=row.get("title", ""),
            tvshow_title=row.get("tvshowtitle") or series_identity["title"],
            tvshow_db_id=tvshow_id,
            season=as_int(row.get("season"), -1),
            episode=as_int(row.get("episode"), -1),
            file_path=row.get("file", ""),
            unique_ids=row.get("uniqueid") or {},
            series_year=series_identity["year"],
            series_unique_ids=series_identity["uniqueid"],
        )
        series = resolve_series(selected, self.manager.sonarr, self.path_mapper)
        _, linked, file_record = resolve_episode_context(selected, self.manager.sonarr, series)
        watched = as_int(row.get("playcount")) > 0
        return RetentionCandidate(
            media_type="episode",
            db_id=db_id,
            arr_id=int(series["id"]),
            file_id=as_int(file_record.get("id")) or None,
            title=row.get("title", ""),
            display_name=selected.display_name,
            watched=watched,
            last_played=self._parse_kodi_date(row.get("lastplayed")) if watched else None,
            date_added=self._conservative_added(
                self._parse_kodi_date(row.get("dateadded")),
                self._parse_arr_date(file_record.get("dateAdded")),
            ),
            unique_ids=selected.unique_ids,
            season=selected.season,
            episode=selected.episode,
            file_path=selected.file_path,
            tvshow_db_id=tvshow_id,
            series_title=selected.tvshow_title,
        )
