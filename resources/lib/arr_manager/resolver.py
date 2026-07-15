import os

from .errors import ResolutionError
from .util import is_path_under, normalise_path, normalise_title


def _numeric_unique_id(value):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return 0


def _year_from_series(series):
    year = series.get("year") or 0
    try:
        return int(year)
    except (TypeError, ValueError):
        return 0


def resolve_movie(selected, client, mapper):
    tmdb_id = _numeric_unique_id(selected.unique_ids.get("tmdb"))
    selected_path = _safe_selected_path(selected.file_path)
    wanted_title = normalise_title(selected.title)
    if tmdb_id:
        direct = client.movie_by_tmdb(tmdb_id)
        if direct:
            _reject_contradictory_movie(selected, direct, wanted_title)
            return direct

    candidates = client.all_movies()
    selected_remote = mapper.kodi_to_remote(selected_path) if selected_path else ""
    wanted_title = normalise_title(selected.title)
    scored = []
    for movie in candidates:
        score = 0
        reasons = []
        path = normalise_path(movie.get("path", ""))
        if selected_remote and path and is_path_under(selected_remote, path):
            score += 140
            reasons.append("path")
        elif selected_path and path:
            kodi_path = mapper.remote_to_kodi(path)
            if kodi_path and is_path_under(selected_path, kodi_path):
                score += 140
                reasons.append("mapped path")

        title = normalise_title(movie.get("title", ""))
        original = normalise_title(movie.get("originalTitle", ""))
        if wanted_title and wanted_title in {title, original}:
            score += 80
            reasons.append("title")
        movie_year = int(movie.get("year") or 0)
        if selected.year and movie_year and movie_year != selected.year and "path" not in reasons and "mapped path" not in reasons:
            scored.append((0, movie, "year mismatch"))
            continue
        if selected.year and movie_year == selected.year:
            score += 25
            reasons.append("year")
        if reasons == ["title"]:
            score = 0
        scored.append((score, movie, ", ".join(reasons)))

    return _choose_unique(scored, "Radarr movie", selected.display_name)


def resolve_series(selected, client, mapper):
    tvdb_id = _numeric_unique_id(selected.unique_ids.get("tvdb"))
    selected_path = _safe_selected_path(selected.file_path)
    wanted_title = normalise_title(selected.tvshow_title or selected.title)
    if tvdb_id:
        direct = client.series_by_tvdb(tvdb_id)
        if direct:
            _reject_contradictory_series(selected, direct, wanted_title)
            return direct

    candidates = client.all_series()
    selected_remote = mapper.kodi_to_remote(selected_path) if selected_path else ""
    scored = []
    for series in candidates:
        score = 0
        reasons = []
        path = normalise_path(series.get("path", ""))
        if selected_remote and path and is_path_under(selected_remote, path):
            score += 140
            reasons.append("path")
        elif selected_path and path:
            kodi_path = mapper.remote_to_kodi(path)
            if kodi_path and is_path_under(selected_path, kodi_path):
                score += 140
                reasons.append("mapped path")

        title_values = {
            normalise_title(series.get("title", "")),
            normalise_title(series.get("sortTitle", "")),
            normalise_title(series.get("originalTitle", "")),
        }
        title_values.discard("")
        if wanted_title and wanted_title in title_values:
            score += 80
            reasons.append("title")
        series_year = _year_from_series(series)
        if selected.year and series_year and series_year != selected.year and "path" not in reasons and "mapped path" not in reasons:
            scored.append((0, series, "year mismatch"))
            continue
        if selected.year and series_year == selected.year:
            score += 25
            reasons.append("year")
        if reasons == ["title"]:
            score = 0
        scored.append((score, series, ", ".join(reasons)))

    return _choose_unique(scored, "Sonarr series", selected.display_name)


def resolve_episode_context(selected, client, series):
    if selected.season < 0 or selected.episode < 0:
        raise ResolutionError("Kodi did not expose a valid season and episode number")
    episodes = client.episodes(series["id"], selected.season)
    matches = [
        episode for episode in episodes
        if int(episode.get("seasonNumber", -999)) == selected.season
        and int(episode.get("episodeNumber", -999)) == selected.episode
    ]
    if len(matches) != 1:
        raise ResolutionError(
            f"Expected one Sonarr episode for S{selected.season:02d}E{selected.episode:02d}; found {len(matches)}"
        )
    episode = matches[0]
    file_id = int(episode.get("episodeFileId") or 0)
    if not file_id:
        raise ResolutionError("The selected Sonarr episode has no episode file")
    all_episodes = client.episodes(series["id"])
    linked = [item for item in all_episodes if int(item.get("episodeFileId") or 0) == file_id]
    files = client.episode_files(series["id"])
    file_matches = [item for item in files if int(item.get("id") or 0) == file_id]
    if len(file_matches) != 1:
        raise ResolutionError(f"Could not resolve Sonarr episode file ID {file_id}")
    return episode, linked, file_matches[0]



def _safe_selected_path(path):
    if not path:
        return ""
    try:
        return normalise_path(path)
    except ValueError as exc:
        raise ResolutionError(str(exc)) from exc


def _reject_contradictory_movie(selected, movie, wanted_title):
    if selected.year and int(movie.get("year") or 0) and int(movie.get("year") or 0) != selected.year:
        raise ResolutionError("Kodi movie year contradicts the matched Radarr movie")
    if wanted_title:
        titles = {normalise_title(movie.get("title", "")), normalise_title(movie.get("originalTitle", ""))} - {""}
        if titles and wanted_title not in titles:
            raise ResolutionError("Kodi movie title contradicts the matched Radarr movie")


def _reject_contradictory_series(selected, series, wanted_title):
    series_year = _year_from_series(series)
    if selected.year and series_year and series_year != selected.year:
        raise ResolutionError("Kodi series year contradicts the matched Sonarr series")
    if wanted_title:
        titles = {normalise_title(series.get("title", "")), normalise_title(series.get("sortTitle", "")), normalise_title(series.get("originalTitle", ""))} - {""}
        if titles and wanted_title not in titles:
            raise ResolutionError("Kodi series title contradicts the matched Sonarr series")

def _choose_unique(scored, entity_name, display_name):
    scored.sort(key=lambda row: row[0], reverse=True)
    if not scored or scored[0][0] < 80:
        raise ResolutionError(f"Could not confidently match {display_name} to a {entity_name}")
    best = scored[0]
    if len(scored) > 1 and scored[1][0] == best[0]:
        raise ResolutionError(f"Multiple {entity_name} matches have the same confidence for {display_name}")
    return best[1]
