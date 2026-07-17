# SPDX-License-Identifier: GPL-3.0-or-later
from .errors import ResolutionError
from .resolver import resolve_episode, resolve_movie, resolve_series


class ManagementMixin:
    def status(self, selected):
        if selected.media_type == "movie":
            entity = resolve_movie(selected, self.radarr, self.settings.path_mapper)
            status = self.radarr.status()
            profile = self._profile_name(self.radarr.quality_profiles(), entity.get("qualityProfileId"))
            files = self.radarr.movie_files(entity["id"])
            return self._m(
                "movie_status", version=status.get("version", "unknown"),
                title=entity.get("title", selected.title),
                monitoring=self._m("monitored") if entity.get("monitored") else self._m("unmonitored"),
                profile=profile, files=len(files),
            )
        series = resolve_series(selected, self.sonarr, self.settings.path_mapper)
        status = self.sonarr.status()
        profile = self._profile_name(self.sonarr.quality_profiles(), series.get("qualityProfileId"))
        if selected.media_type == "episode":
            episode = resolve_episode(selected, self.sonarr, series)
            return self._m(
                "episode_status", version=status.get("version", "unknown"),
                season=selected.season, episode=selected.episode,
                monitoring=self._m("monitored") if episode.get("monitored") else self._m("unmonitored"),
                file_state=self._m("available") if int(episode.get("episodeFileId") or 0) else self._m("missing"),
                profile=profile,
            )
        files = self.sonarr.episode_files(series["id"])
        return self._m(
            "series_status", version=status.get("version", "unknown"),
            title=series.get("title", selected.title),
            monitoring=self._m("monitored") if series.get("monitored") else self._m("unmonitored"),
            profile=profile, files=len(files),
        )

    def search_now(self, selected):
        if selected.media_type == "movie":
            movie = resolve_movie(selected, self.radarr, self.settings.path_mapper)
            self._queue_search(self.radarr, self.radarr.search_movie(movie["id"]), "Radarr movie search")
            return self._m("search_movie_done", title=movie.get("title"))
        series = resolve_series(selected, self.sonarr, self.settings.path_mapper)
        if selected.media_type == "tvshow":
            self._queue_search(self.sonarr, self.sonarr.search_series(series["id"]), "Sonarr series search")
            return self._m("search_series_done", title=series.get("title"))
        episode = resolve_episode(selected, self.sonarr, series)
        self._queue_search(self.sonarr, self.sonarr.search_episodes([episode["id"]]), "Sonarr episode search")
        return self._m("search_episode_done", title=series.get("title"), season=selected.season, episode=selected.episode)

    def set_monitoring(self, selected, monitored):
        label = self._m("monitored") if monitored else self._m("unmonitored")
        if selected.media_type == "movie":
            movie = dict(resolve_movie(selected, self.radarr, self.settings.path_mapper))
            movie["monitored"] = bool(monitored)
            self.radarr.update_movie(movie)
            return self._m("monitor_movie_done", title=movie.get("title"), state=label)
        series = dict(resolve_series(selected, self.sonarr, self.settings.path_mapper))
        if selected.media_type == "episode":
            episode = dict(resolve_episode(selected, self.sonarr, series))
            episode["monitored"] = bool(monitored)
            self.sonarr.update_episode(episode)
            return self._m("monitor_episode_done", title=series.get("title"), season=selected.season, episode=selected.episode, state=label)
        series["monitored"] = bool(monitored)
        seasons = []
        for season in series.get("seasons") or []:
            if isinstance(season, dict):
                updated = dict(season)
                updated["monitored"] = bool(monitored)
                seasons.append(updated)
        if seasons:
            series["seasons"] = seasons
        self.sonarr.update_series(series)
        return self._m("monitor_series_done", title=series.get("title"), state=label)

    def quality_profiles(self, selected):
        client = self.radarr if selected.media_type == "movie" else self.sonarr
        profiles = []
        for profile in client.quality_profiles():
            try:
                profile_id = int(profile.get("id") or 0)
            except (TypeError, ValueError):
                profile_id = 0
            name = str(profile.get("name") or "").strip()
            if profile_id > 0 and name:
                profiles.append({"id": profile_id, "name": name})
        if not profiles:
            raise ResolutionError(self._m("no_quality_profiles"))
        return sorted(profiles, key=lambda item: item["name"].lower())

    def change_quality_profile(self, selected, profile_id):
        profile_id = int(profile_id)
        if not any(item["id"] == profile_id for item in self.quality_profiles(selected)):
            raise ResolutionError(self._m("quality_profile_missing"))
        if selected.media_type == "movie":
            movie = dict(resolve_movie(selected, self.radarr, self.settings.path_mapper))
            movie["qualityProfileId"] = profile_id
            self.radarr.update_movie(movie)
            return self._m("quality_movie_done", title=movie.get("title"))
        series = dict(resolve_series(selected, self.sonarr, self.settings.path_mapper))
        series["qualityProfileId"] = profile_id
        self.sonarr.update_series(series)
        key = "quality_episode_scope" if selected.media_type == "episode" else "quality_series_done"
        return self._m(key, title=series.get("title"))

    def queue_entries(self, selected):
        if selected.media_type == "movie":
            movie = resolve_movie(selected, self.radarr, self.settings.path_mapper)
            return [self._queue_summary(row, "Radarr") for row in self.radarr.queue(movie["id"])]
        series = resolve_series(selected, self.sonarr, self.settings.path_mapper)
        rows = self.sonarr.queue(series["id"])
        if selected.media_type == "episode":
            episode = resolve_episode(selected, self.sonarr, series)
            episode_id = int(episode["id"])
            rows = [row for row in rows if episode_id in self._queue_episode_ids(row)]
        return [self._queue_summary(row, "Sonarr") for row in rows]

    def remove_queue_item(self, selected, queue_id):
        entries = self.queue_entries(selected)
        matches = [entry for entry in entries if entry["id"] == int(queue_id)]
        if len(matches) != 1:
            raise ResolutionError(self._m("queue_item_missing"))
        entry = matches[0]
        prompt = self._m("queue_remove_confirm", title=entry["title"])
        if not self.ui.confirm(self._m("queue_remove_heading"), prompt):
            return self._m("cancelled")
        client = self.radarr if entry["service"] == "Radarr" else self.sonarr
        client.remove_queue_item(entry["id"], remove_from_client=True, blocklist=False)
        return self._m("queue_removed", title=entry["title"], service=entry["service"])

    @staticmethod
    def _queue_episode_ids(row):
        ids = set()
        candidates = [row.get("episodeId")]
        candidates.extend(row.get("episodeIds") or [] if isinstance(row.get("episodeIds"), list) else [])
        episode = row.get("episode") if isinstance(row.get("episode"), dict) else {}
        candidates.append(episode.get("id"))
        for item in row.get("episodes") or [] if isinstance(row.get("episodes"), list) else []:
            if isinstance(item, dict):
                candidates.append(item.get("id"))
        for value in candidates:
            try:
                value = int(value or 0)
            except (TypeError, ValueError):
                continue
            if value > 0:
                ids.add(value)
        return ids

    def _queue_summary(self, row, service):
        queue_id = int(row.get("id") or 0)
        if queue_id <= 0:
            raise ResolutionError(self._m("queue_item_missing"))
        title = str(row.get("title") or row.get("downloadTitle") or self._m("queue_unnamed"))
        status = str(row.get("status") or "unknown")
        tracked = str(row.get("trackedDownloadStatus") or "")
        time_left = str(row.get("timeleft") or "")
        size = float(row.get("size") or 0)
        size_left = float(row.get("sizeleft") or 0)
        progress = 0
        if size > 0:
            progress = max(0, min(100, round((size - size_left) / size * 100)))
        tracked_text = self._m("queue_tracked", tracked=tracked) if tracked and tracked.lower() != status.lower() else ""
        remaining_text = self._m("queue_remaining", time_left=time_left) if time_left else ""
        detail = self._m("queue_detail", status=status, tracked=tracked_text, progress=progress, remaining=remaining_text)
        return {"id": queue_id, "title": title, "status": status, "detail": detail, "service": service, "raw": row}

    def _profile_name(self, profiles, profile_id):
        for profile in profiles:
            if int(profile.get("id") or 0) == int(profile_id or 0):
                name = str(profile.get("name") or "").strip()
                return name or self._m("profile_unknown", profile_id=profile_id or "unknown")
        return self._m("profile_unknown", profile_id=profile_id or "unknown")
