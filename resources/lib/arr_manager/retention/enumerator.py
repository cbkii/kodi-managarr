# SPDX-License-Identifier: GPL-3.0-or-later
import datetime
import math

from ..errors import ResolutionError, SafetyError
from ..models import SelectedItem
from ..resolver import resolve_movie, resolve_series
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
        self._kodi_series_cache = {}
        self._sonarr_context_cache = {}

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
                        self.logger.debug(
                            "Retention skipped unresolved Kodi item %s: %s",
                            row.get("label") or row.get("title"),
                            exc,
                        )
                    continue
                except Exception as exc:
                    if self.logger:
                        self.logger.warning(
                            "Retention skipped malformed Kodi item %s: %s",
                            row.get("label") or row.get("title"),
                            exc,
                        )
                    continue
                if candidate:
                    candidates.append(candidate)
            start += self.PAGE_SIZE
            if len(rows) < self.PAGE_SIZE:
                break
        return candidates

    @staticmethod
    def _parse_kodi_date(value):
        if value is None or value == "":
            return None
        text = str(value).strip()
        if not text:
            raise SafetyError("Kodi supplied an invalid blank retention timestamp")
        try:
            parsed = datetime.datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
        except ValueError as exc:
            raise SafetyError("Kodi supplied an invalid retention timestamp") from exc
        return parsed.replace(tzinfo=datetime.timezone.utc).timestamp()

    @staticmethod
    def _parse_arr_date(value):
        if value is None or value == "":
            return None
        text = str(value).strip()
        if not text:
            raise SafetyError("Arr supplied an invalid blank retention timestamp")
        text = text.replace("Z", "+00:00")
        try:
            parsed = datetime.datetime.fromisoformat(text)
        except ValueError:
            try:
                parsed = datetime.datetime.strptime(text.split(".", 1)[0], "%Y-%m-%dT%H:%M:%S")
            except ValueError as exc:
                raise SafetyError("Arr supplied an invalid retention timestamp") from exc
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=datetime.timezone.utc)
        return parsed.timestamp()

    @staticmethod
    def _conservative_added(*timestamps):
        valid = []
        for value in timestamps:
            if value is None:
                continue
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise SafetyError("Retention timestamp type is invalid")
            value = float(value)
            if not math.isfinite(value) or value <= 0:
                raise SafetyError("Retention timestamp value is invalid")
            valid.append(value)
        return max(valid) if valid else None

    @staticmethod
    def _rating(value):
        try:
            result = float(value)
        except (TypeError, ValueError):
            return None
        return result if math.isfinite(result) and 0 < result <= 10 else None

    @staticmethod
    def _positive_id(value, description):
        result = as_int(value)
        if result <= 0:
            raise SafetyError(f"{description} did not contain a positive ID")
        return result

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
        movie_id = self._positive_id(movie.get("id"), "Radarr movie")
        if not movie.get("hasFile"):
            return None
        files = self.manager.radarr.movie_files(movie_id)
        if len(files) != 1:
            raise ResolutionError(
                f"Expected one Radarr movie file for {selected.display_name}; found {len(files)}"
            )
        file_record = files[0]
        file_id = self._positive_id(file_record.get("id"), "Radarr movie file")
        watched = as_int(row.get("playcount")) > 0
        return RetentionCandidate(
            media_type="movie",
            db_id=db_id,
            arr_id=movie_id,
            file_id=file_id,
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

    def _series_identity(self, tvshow_id, refresh=False):
        if not refresh and tvshow_id in self._kodi_series_cache:
            return self._kodi_series_cache[tvshow_id]
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
        self._kodi_series_cache[tvshow_id] = identity
        return identity

    def _series_context(self, selected, refresh=False, sonarr_snapshot=None):
        cache_key = int(selected.tvshow_db_id)
        if not refresh and cache_key in self._sonarr_context_cache:
            return self._sonarr_context_cache[cache_key]
        if sonarr_snapshot is None:
            series = resolve_series(selected, self.manager.sonarr, self.path_mapper)
            series_id = self._positive_id(series.get("id"), "Sonarr series")
            episodes = self.manager.sonarr.episodes(series_id)
            files = self.manager.sonarr.episode_files(series_id)
        else:
            try:
                series, episodes, files = sonarr_snapshot
            except (TypeError, ValueError) as exc:
                raise SafetyError("Sonarr retention snapshot is malformed") from exc
            series_id = self._positive_id(series.get("id"), "Sonarr series")
        if not isinstance(series, dict):
            raise SafetyError("Sonarr series snapshot is malformed")
        if not isinstance(episodes, list) or any(not isinstance(item, dict) for item in episodes):
            raise SafetyError("Sonarr episode snapshot is malformed")
        if not isinstance(files, list) or any(not isinstance(item, dict) for item in files):
            raise SafetyError("Sonarr episode-file snapshot is malformed")

        episode_by_number = {}
        linked_by_file = {}
        for episode in episodes:
            number = (as_int(episode.get("seasonNumber"), -1), as_int(episode.get("episodeNumber"), -1))
            if number[0] < 0 or number[1] < 0 or number in episode_by_number:
                raise SafetyError("Sonarr episode numbering is malformed or duplicated")
            self._positive_id(episode.get("id"), "Sonarr episode")
            episode_by_number[number] = episode
            file_id = as_int(episode.get("episodeFileId"))
            if file_id > 0:
                linked_by_file.setdefault(file_id, []).append(episode)

        file_by_id = {}
        for file_record in files:
            file_id = self._positive_id(file_record.get("id"), "Sonarr episode file")
            if file_id in file_by_id:
                raise SafetyError("Sonarr returned duplicate episode-file IDs")
            file_by_id[file_id] = file_record

        context = {
            "series": series,
            "series_id": series_id,
            "episode_by_number": episode_by_number,
            "linked_by_file": linked_by_file,
            "file_by_id": file_by_id,
        }
        self._sonarr_context_cache[cache_key] = context
        return context

    def _process_kodi_episode(self, row, refresh=False, sonarr_snapshot=None):
        db_id = as_int(row.get("episodeid"))
        tvshow_id = as_int(row.get("tvshowid"))
        if db_id <= 0 or tvshow_id <= 0:
            return None
        series_identity = self._series_identity(tvshow_id, refresh=refresh)
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
        if selected.season < 0 or selected.episode < 0:
            return None
        context = self._series_context(
            selected,
            refresh=refresh,
            sonarr_snapshot=sonarr_snapshot,
        )
        episode_record = context["episode_by_number"].get((selected.season, selected.episode))
        if episode_record is None:
            raise ResolutionError(f"Sonarr episode was not found for {selected.display_name}")
        file_id = as_int(episode_record.get("episodeFileId"))
        if file_id <= 0:
            return None
        file_record = context["file_by_id"].get(file_id)
        linked = context["linked_by_file"].get(file_id) or []
        if file_record is None or not linked:
            raise SafetyError("Sonarr episode-file linkage is incomplete")
        watched = as_int(row.get("playcount")) > 0
        series = context["series"]
        return RetentionCandidate(
            media_type="episode",
            db_id=db_id,
            arr_id=context["series_id"],
            file_id=file_id,
            title=row.get("title", ""),
            display_name=selected.display_name,
            watched=watched,
            last_played=self._parse_kodi_date(row.get("lastplayed")) if watched else None,
            date_added=self._conservative_added(
                self._parse_kodi_date(row.get("dateadded")),
                self._parse_arr_date(series.get("added")),
                self._parse_arr_date(file_record.get("dateAdded")),
            ),
            unique_ids=selected.unique_ids,
            season=selected.season,
            episode=selected.episode,
            file_path=selected.file_path,
            tvshow_db_id=tvshow_id,
            series_title=selected.tvshow_title,
            linked_episode_count=len(linked),
        )
