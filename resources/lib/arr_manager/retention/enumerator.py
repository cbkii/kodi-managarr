# SPDX-License-Identifier: GPL-3.0-or-later
from datetime import datetime, timezone

from ..errors import ResolutionError, SafetyError
from ..models import SelectedItem
from ..resolver import resolve_episode_context, resolve_movie, resolve_series
from ..util import as_int
from .models import RetentionCandidate


class RetentionEnumerator:
    PAGE_SIZE = 200
    MOVIE_PROPERTIES = ["title", "year", "file", "uniqueid", "playcount", "lastplayed", "dateadded", "rating"]
    EPISODE_PROPERTIES = [
        "title", "season", "episode", "file", "tvshowid", "tvshowtitle", "playcount", "lastplayed",
        "dateadded", "uniqueid",
    ]

    def __init__(self, kodi_client, manager, path_mapper, logger=None):
        self.kodi = kodi_client
        self.manager = manager
        self.path_mapper = path_mapper
        self.logger = logger
        self.skipped = {}

    def _skip(self, reason):
        self.skipped[reason] = self.skipped.get(reason, 0) + 1

    @staticmethod
    def parse_timestamp(value):
        text = str(value or "").strip()
        if not text:
            return None
        try:
            if text.endswith("Z"):
                text = text[:-1] + "+00:00"
            parsed = datetime.fromisoformat(text)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc).timestamp()
        except (TypeError, ValueError, OverflowError):
            return None

    @staticmethod
    def conservative_added(*values):
        valid = [float(value) for value in values if value is not None and float(value) > 0]
        return max(valid) if valid else None

    @staticmethod
    def movie_ratings(kodi_row, radarr_row):
        ratings = {}
        try:
            kodi_rating = float(kodi_row.get("rating"))
            if 0 <= kodi_rating <= 10:
                ratings["kodi"] = kodi_rating
        except (TypeError, ValueError):
            pass
        raw = radarr_row.get("ratings")
        if isinstance(raw, dict):
            for source, item in raw.items():
                value = item.get("value") if isinstance(item, dict) else item
                try:
                    score = float(value)
                except (TypeError, ValueError):
                    continue
                source_name = str(source or "").lower()
                if 0 <= score <= 10:
                    ratings[f"radarr:{source_name}"] = score
                elif "rotten" in source_name and 0 <= score <= 100:
                    ratings[f"radarr:{source_name}"] = score / 10.0
        return ratings

    def iter_candidates(self, settings):
        self.skipped = {}
        if settings.include_movies:
            yield from self._iter_library("VideoLibrary.GetMovies", "movies", "movieid", self.MOVIE_PROPERTIES,
                                          self._movie_candidate)
        if settings.include_episodes:
            yield from self._iter_library("VideoLibrary.GetEpisodes", "episodes", "episodeid", self.EPISODE_PROPERTIES,
                                          self._episode_candidate)

    def _iter_library(self, method, key, id_key, properties, processor):
        start = 0
        while True:
            response = self.kodi.call(method, {
                "properties": properties,
                "limits": {"start": start, "end": start + self.PAGE_SIZE},
            })
            if not isinstance(response, dict):
                raise SafetyError(f"Kodi {method} returned a malformed response")
            rows = response.get(key) or []
            if not isinstance(rows, list):
                raise SafetyError(f"Kodi {method} returned malformed records")
            for row in rows:
                if not isinstance(row, dict) or as_int(row.get(id_key)) <= 0:
                    self._skip("invalid_kodi_record")
                    continue
                try:
                    candidate = processor(row)
                except ResolutionError:
                    self._skip("unresolved")
                    continue
                except Exception as exc:
                    self._skip(type(exc).__name__)
                    if self.logger:
                        self.logger.debug("Retention skipped %s %s: %s", key, row.get(id_key), type(exc).__name__)
                    continue
                if candidate:
                    yield candidate
                else:
                    self._skip("no_file")
            limits = response.get("limits") if isinstance(response.get("limits"), dict) else {}
            total = as_int(limits.get("total"), start + len(rows))
            start += len(rows)
            if not rows or start >= total or len(rows) < self.PAGE_SIZE:
                break

    def candidate_by_id(self, media_type, db_id):
        if media_type == "movie":
            response = self.kodi.call("VideoLibrary.GetMovieDetails", {
                "movieid": int(db_id), "properties": self.MOVIE_PROPERTIES,
            })
            row = response.get("moviedetails") if isinstance(response, dict) else None
            return self._movie_candidate(row) if isinstance(row, dict) else None
        if media_type == "episode":
            response = self.kodi.call("VideoLibrary.GetEpisodeDetails", {
                "episodeid": int(db_id), "properties": self.EPISODE_PROPERTIES,
            })
            row = response.get("episodedetails") if isinstance(response, dict) else None
            return self._episode_candidate(row) if isinstance(row, dict) else None
        return None

    def _movie_candidate(self, row):
        selected = SelectedItem(
            media_type="movie", db_id=as_int(row.get("movieid")), title=str(row.get("title") or ""),
            year=as_int(row.get("year")), file_path=str(row.get("file") or ""),
            unique_ids=dict(row.get("uniqueid") or {}),
        )
        movie = resolve_movie(selected, self.manager.radarr, self.path_mapper)
        files = self.manager.radarr.movie_files(movie["id"])
        if not isinstance(files, list) or len(files) != 1:
            return None
        file_record = files[0]
        file_id = as_int(file_record.get("id"))
        if file_id <= 0:
            return None
        ratings = self.movie_ratings(row, movie)
        watched = as_int(row.get("playcount")) > 0
        return RetentionCandidate(
            media_type="movie", db_id=selected.db_id, arr_id=as_int(movie.get("id")), file_id=file_id,
            title=selected.title, display_name=selected.display_name, watched=watched,
            last_played=self.parse_timestamp(row.get("lastplayed")) if watched else None,
            date_added=self.conservative_added(
                self.parse_timestamp(row.get("dateadded")), self.parse_timestamp(movie.get("added")),
                self.parse_timestamp(file_record.get("dateAdded")),
            ),
            unique_ids=selected.unique_ids,
            rating=max(ratings.values()) if ratings else None,
            rating_sources=ratings,
        )

    def _episode_candidate(self, row):
        selected = SelectedItem(
            media_type="episode", db_id=as_int(row.get("episodeid")), title=str(row.get("title") or ""),
            tvshow_title=str(row.get("tvshowtitle") or ""), tvshow_db_id=as_int(row.get("tvshowid")),
            season=as_int(row.get("season"), -1), episode=as_int(row.get("episode"), -1),
            file_path=str(row.get("file") or ""), unique_ids=dict(row.get("uniqueid") or {}),
        )
        series = resolve_series(selected, self.manager.sonarr, self.path_mapper)
        _, linked, file_record = resolve_episode_context(selected, self.manager.sonarr, series)
        if not linked or not file_record:
            return None
        file_id = as_int(file_record.get("id"))
        if file_id <= 0:
            return None
        watched = as_int(row.get("playcount")) > 0
        return RetentionCandidate(
            media_type="episode", db_id=selected.db_id, arr_id=as_int(series.get("id")), file_id=file_id,
            title=selected.title, display_name=selected.display_name, watched=watched,
            last_played=self.parse_timestamp(row.get("lastplayed")) if watched else None,
            date_added=self.conservative_added(
                self.parse_timestamp(row.get("dateadded")), self.parse_timestamp(file_record.get("dateAdded")),
            ),
            unique_ids=selected.unique_ids,
            series_tvdb_id=as_int(series.get("tvdbId")), season=selected.season, episode=selected.episode,
        )
