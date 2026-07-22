# SPDX-License-Identifier: GPL-3.0-or-later
from collections import OrderedDict
from datetime import datetime, timezone

from ..errors import ApiError, ResolutionError
from ..kodi_jsonrpc import KodiJsonRpcError
from ..models import SelectedItem
from ..resolver import resolve_episode_context, resolve_movie, resolve_series
from ..util import as_int
from .models import RetentionCandidate, RetentionScanResult


class RetentionEnumerator:
    MOVIE_PROPERTIES = (
        "title", "year", "file", "uniqueid", "playcount", "lastplayed", "dateadded",
    )
    EPISODE_PROPERTIES = (
        "title", "season", "episode", "file", "tvshowid", "tvshowtitle",
        "playcount", "lastplayed", "dateadded", "uniqueid",
    )
    TVSHOW_PROPERTIES = ("title", "year", "uniqueid")
    PAGE_SIZE = 200
    SERIES_CACHE_SIZE = 4
    TVSHOW_CACHE_SIZE = 16

    def __init__(self, kodi_client, arr_manager, path_mapper, logger=None):
        self.kodi = kodi_client
        self.manager = arr_manager
        self.path_mapper = path_mapper
        self.logger = logger
        self._series_episode_cache = OrderedDict()
        self._tvshow_cache = OrderedDict()

    @staticmethod
    def parse_kodi_date(value):
        text = str(value or "").strip()
        if not text:
            return None
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
            try:
                # Kodi exposes these values without an offset. datetime.timestamp()
                # consistently interprets them in Kodi/Python's local timezone.
                return datetime.strptime(text, fmt).timestamp()
            except ValueError:
                continue
        return None

    @staticmethod
    def parse_servarr_date(value):
        text = str(value or "").strip()
        if not text:
            return None
        try:
            normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
            parsed = datetime.fromisoformat(normalized)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.timestamp()
        except (TypeError, ValueError, OverflowError):
            return None

    @staticmethod
    def conservative_added(*timestamps):
        valid = [float(value) for value in timestamps if value is not None and float(value) > 0]
        return max(valid) if valid else None

    def _paged(self, method, key, properties, extra=None):
        start = 0
        extra = dict(extra or {})
        while True:
            params = dict(extra)
            params["properties"] = list(properties)
            params["limits"] = {"start": start, "end": start + self.PAGE_SIZE}
            result = self.kodi.call(method, params)
            if not isinstance(result, dict):
                raise KodiJsonRpcError(f"Kodi JSON-RPC returned malformed {key} page")
            rows = result.get(key, [])
            if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
                raise KodiJsonRpcError(f"Kodi JSON-RPC returned malformed {key}")
            for row in rows:
                yield row
            if not rows:
                break
            limits = result.get("limits")
            if isinstance(limits, dict):
                end = as_int(limits.get("end"), start + len(rows))
                total = as_int(limits.get("total"), end)
            else:
                end = start + len(rows)
                total = end if len(rows) < self.PAGE_SIZE else end + 1
            if end <= start:
                raise KodiJsonRpcError(f"Kodi JSON-RPC {key} pagination did not advance")
            if end >= total or len(rows) < self.PAGE_SIZE:
                break
            start = end

    def iter_scan_results(self, settings):
        if settings.include_movies:
            for row in self._paged("VideoLibrary.GetMovies", "movies", self.MOVIE_PROPERTIES):
                try:
                    candidate = self._movie_candidate(row)
                    yield RetentionScanResult(candidate=candidate) if candidate else RetentionScanResult(
                        skipped_reason="movie_without_single_file"
                    )
                except ResolutionError:
                    yield RetentionScanResult(skipped_reason="movie_unmanaged_or_ambiguous")
                except ApiError:
                    raise
                except Exception as exc:
                    self._log_skip("movie", row.get("movieid"), exc)
                    yield RetentionScanResult(skipped_reason="movie_invalid")

        if settings.include_episodes:
            seen_files = set()
            for row in self._paged("VideoLibrary.GetEpisodes", "episodes", self.EPISODE_PROPERTIES):
                try:
                    candidate = self._episode_candidate(row)
                    if candidate is None:
                        yield RetentionScanResult(skipped_reason="episode_without_file")
                        continue
                    key = (candidate.arr_id, candidate.file_id)
                    if key in seen_files:
                        continue
                    seen_files.add(key)
                    yield RetentionScanResult(candidate=candidate)
                except ResolutionError:
                    yield RetentionScanResult(skipped_reason="episode_unmanaged_or_ambiguous")
                except ApiError:
                    raise
                except Exception as exc:
                    self._log_skip("episode", row.get("episodeid"), exc)
                    yield RetentionScanResult(skipped_reason="episode_invalid")

    def _log_skip(self, media_type, db_id, exc):
        if self.logger:
            self.logger.debug(
                "Skipped retention %s row %s because %s",
                media_type,
                int(db_id or 0),
                type(exc).__name__,
            )

    @staticmethod
    def _unique_ids(row):
        value = row.get("uniqueid")
        return dict(value) if isinstance(value, dict) else {}

    def _movie_candidate(self, row):
        db_id = as_int(row.get("movieid"))
        if db_id <= 0:
            return None
        selected = SelectedItem(
            media_type="movie",
            db_id=db_id,
            title=str(row.get("title") or ""),
            year=as_int(row.get("year")),
            file_path=str(row.get("file") or ""),
            unique_ids=self._unique_ids(row),
        )
        movie = resolve_movie(selected, self.manager.radarr, self.path_mapper)
        files = self.manager.radarr.movie_files(movie["id"])
        if len(files) != 1:
            return None
        file_record = files[0]
        file_id = as_int(file_record.get("id"))
        if file_id <= 0:
            return None
        watched = as_int(row.get("playcount")) > 0
        last_played = self.parse_kodi_date(row.get("lastplayed")) if watched else None
        date_added = self.conservative_added(
            self.parse_kodi_date(row.get("dateadded")),
            self.parse_servarr_date(movie.get("added")),
            self.parse_servarr_date(file_record.get("dateAdded")),
        )
        return RetentionCandidate(
            media_type="movie",
            kodi_db_ids=(db_id,),
            arr_id=as_int(movie.get("id")),
            file_id=file_id,
            title=str(movie.get("title") or selected.title),
            display_name=selected.display_name,
            watched=watched,
            last_played=last_played,
            date_added=date_added,
            unique_ids=selected.unique_ids,
            file_path=selected.file_path,
        )

    def _episode_candidate(self, row):
        db_id = as_int(row.get("episodeid"))
        if db_id <= 0:
            return None
        tvshow_id = as_int(row.get("tvshowid"))
        show = self._tvshow_identity(tvshow_id, str(row.get("tvshowtitle") or ""))
        selected = SelectedItem(
            media_type="episode",
            db_id=db_id,
            title=str(row.get("title") or ""),
            year=as_int(show.get("year")),
            tvshow_title=str(show.get("title") or row.get("tvshowtitle") or ""),
            tvshow_db_id=tvshow_id,
            season=as_int(row.get("season"), -1),
            episode=as_int(row.get("episode"), -1),
            file_path=str(row.get("file") or ""),
            unique_ids=self._unique_ids(show),
        )
        series = resolve_series(selected, self.manager.sonarr, self.path_mapper)
        _episode, linked, file_record = resolve_episode_context(selected, self.manager.sonarr, series)
        file_id = as_int(file_record.get("id"))
        if file_id <= 0 or not linked:
            return None

        linked_numbers = {
            (as_int(item.get("seasonNumber"), -1), as_int(item.get("episodeNumber"), -1))
            for item in linked
        }
        kodi_rows = self._linked_kodi_rows(selected.tvshow_db_id, linked_numbers, row)
        represented = {
            (as_int(item.get("season"), -1), as_int(item.get("episode"), -1))
            for item in kodi_rows
        }
        complete = linked_numbers.issubset(represented)
        watched = complete and all(as_int(item.get("playcount")) > 0 for item in kodi_rows)
        played_values = [self.parse_kodi_date(item.get("lastplayed")) for item in kodi_rows]
        last_played = max(played_values) if watched and played_values and all(played_values) else None
        added_values = [self.parse_kodi_date(item.get("dateadded")) for item in kodi_rows]
        date_added = self.conservative_added(
            self.parse_servarr_date(file_record.get("dateAdded")),
            *added_values,
        )
        kodi_ids = tuple(sorted({as_int(item.get("episodeid")) for item in kodi_rows if as_int(item.get("episodeid")) > 0}))
        linked_ids = tuple(sorted({as_int(item.get("id")) for item in linked if as_int(item.get("id")) > 0}))
        episode_labels = ", ".join(
            f"S{season:02d}E{episode:02d}" for season, episode in sorted(linked_numbers)
        )
        show_title = str(series.get("title") or selected.tvshow_title or selected.title)
        return RetentionCandidate(
            media_type="episode",
            kodi_db_ids=kodi_ids or (db_id,),
            arr_id=as_int(series.get("id")),
            file_id=file_id,
            title=selected.title,
            display_name=f"{show_title} {episode_labels}".strip(),
            watched=watched,
            last_played=last_played,
            date_added=date_added,
            unique_ids=selected.unique_ids,
            linked_episode_ids=linked_ids,
            season=selected.season,
            episode=selected.episode,
            tvshow_title=show_title,
            file_path=selected.file_path,
        )

    def _tvshow_identity(self, tvshow_id, fallback_title=""):
        if tvshow_id <= 0:
            return {"title": fallback_title, "year": 0, "uniqueid": {}}
        cached = self._tvshow_cache.get(tvshow_id)
        if cached is not None:
            self._tvshow_cache.move_to_end(tvshow_id)
            return cached
        result = self.kodi.call(
            "VideoLibrary.GetTVShowDetails",
            {"tvshowid": tvshow_id, "properties": list(self.TVSHOW_PROPERTIES)},
        )
        if not isinstance(result, dict) or not isinstance(result.get("tvshowdetails"), dict):
            raise KodiJsonRpcError("Kodi returned malformed TV show identity details")
        detail = result["tvshowdetails"]
        cached = {
            "title": str(detail.get("title") or fallback_title),
            "year": as_int(detail.get("year")),
            "uniqueid": self._unique_ids(detail),
        }
        self._tvshow_cache[tvshow_id] = cached
        self._tvshow_cache.move_to_end(tvshow_id)
        while len(self._tvshow_cache) > self.TVSHOW_CACHE_SIZE:
            self._tvshow_cache.popitem(last=False)
        return cached

    def _linked_kodi_rows(self, tvshow_id, linked_numbers, fallback):
        if tvshow_id <= 0:
            return [fallback]
        cached = self._series_episode_cache.get(tvshow_id)
        if cached is None:
            rows = list(self._paged(
                "VideoLibrary.GetEpisodes",
                "episodes",
                self.EPISODE_PROPERTIES,
                {"tvshowid": tvshow_id},
            ))
            self._series_episode_cache[tvshow_id] = rows
            self._series_episode_cache.move_to_end(tvshow_id)
            while len(self._series_episode_cache) > self.SERIES_CACHE_SIZE:
                self._series_episode_cache.popitem(last=False)
            cached = rows
        else:
            self._series_episode_cache.move_to_end(tvshow_id)
        matched = [
            row for row in cached
            if (as_int(row.get("season"), -1), as_int(row.get("episode"), -1)) in linked_numbers
        ]
        return matched or [fallback]

    def revalidate(self, candidate):
        if candidate.media_type == "movie":
            result = self.kodi.call(
                "VideoLibrary.GetMovieDetails",
                {"movieid": candidate.primary_kodi_id, "properties": list(self.MOVIE_PROPERTIES)},
            )
            if not isinstance(result, dict) or not isinstance(result.get("moviedetails"), dict):
                raise KodiJsonRpcError("Kodi movie disappeared during retention revalidation")
            fresh = self._movie_candidate(result["moviedetails"])
        elif candidate.media_type == "episode":
            result = self.kodi.call(
                "VideoLibrary.GetEpisodeDetails",
                {"episodeid": candidate.primary_kodi_id, "properties": list(self.EPISODE_PROPERTIES)},
            )
            if not isinstance(result, dict) or not isinstance(result.get("episodedetails"), dict):
                raise KodiJsonRpcError("Kodi episode disappeared during retention revalidation")
            detail = result["episodedetails"]
            tvshow_id = as_int(detail.get("tvshowid"))
            self._series_episode_cache.pop(tvshow_id, None)
            self._tvshow_cache.pop(tvshow_id, None)
            fresh = self._episode_candidate(detail)
        else:
            raise ResolutionError("Unsupported retention media type")
        if fresh is None:
            raise ResolutionError("Retention candidate no longer resolves to a managed file")
        return fresh
