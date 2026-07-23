# SPDX-License-Identifier: GPL-3.0-or-later
from .errors import ApiError, ConfigurationError, ResolutionError, SafetyError
from .interactive_messages import imessage
from .resolver import resolve_episode
from .util import normalise_title


def _positive_id(value):
    try:
        result = int(value or 0)
    except (TypeError, ValueError):
        return 0
    return result if result > 0 else 0


def _unique_id(selected, key):
    return _positive_id((selected.unique_ids or {}).get(key))


def _series_tvdb_id(selected):
    ids = selected.unique_ids if selected.media_type == "tvshow" else getattr(selected, "series_unique_ids", {})
    return _positive_id((ids or {}).get("tvdb"))


def _series_year(selected):
    return int(selected.year or 0) if selected.media_type == "tvshow" else int(getattr(selected, "series_year", 0) or 0)


def _title_year_match(row, title, year):
    wanted = normalise_title(title)
    titles = {normalise_title(row.get(key, "")) for key in ("title", "originalTitle", "sortTitle")}
    if wanted not in titles:
        return False
    row_year = _positive_id(row.get("year"))
    return not year or not row_year or int(year) == row_year


def _release_key(row):
    return tuple(str(row.get(key) or "") for key in ("guid", "downloadUrl", "indexerId", "title"))


class InteractiveMixin:
    def _im(self, key, **values):
        return imessage(self.ui, key, **values)

    def request_search(self, selected):
        if selected.media_type == "movie":
            return self._request_movie(selected)
        if selected.media_type in {"tvshow", "episode"}:
            return self._request_series_or_episode(selected)
        raise ResolutionError(self._im("request_unsupported"))

    def _managed_movie(self, selected):
        tmdb_id = _unique_id(selected, "tmdb")
        if tmdb_id:
            return self.radarr.movie_by_tmdb(tmdb_id)
        matches = [row for row in self.radarr.all_movies() if _title_year_match(row, selected.title, selected.year)]
        if len(matches) > 1:
            raise ResolutionError(self._im("multiple_exact_movies", title=selected.display_name))
        return matches[0] if matches else None

    def _managed_series(self, selected):
        tvdb_id = _series_tvdb_id(selected)
        if tvdb_id:
            direct = self.sonarr.series_by_tvdb(tvdb_id)
            if direct:
                return direct
        title = selected.tvshow_title or selected.title
        year = _series_year(selected)
        matches = [row for row in self.sonarr.all_series() if _title_year_match(row, title, year)]
        if len(matches) > 1:
            raise ResolutionError(self._im("multiple_exact_series", title=selected.display_name))
        return matches[0] if matches else None

    def _pick_lookup(self, rows, selected, id_key, expected_id, match_title=None, match_year=None):
        if expected_id:
            rows = [row for row in rows if _positive_id(row.get(id_key)) == expected_id]
        else:
            title = match_title if match_title is not None else (selected.tvshow_title or selected.title)
            year = selected.year if match_year is None else match_year
            rows = [row for row in rows if _title_year_match(row, title, year)]
        if not rows:
            raise ResolutionError(self._im("lookup_no_results", title=selected.display_name))
        if len(rows) == 1:
            return rows[0]
        labels = [
            f"{row.get('title') or row.get('originalTitle') or '?'} ({row.get('year') or '?'}) - "
            f"{id_key} {row.get(id_key) or '?'}"
            for row in rows
        ]
        choice = self.ui.select(self._im("lookup_choose"), labels)
        if choice < 0:
            raise ResolutionError(self._m("cancelled"))
        return rows[choice]

    def _request_movie(self, selected):
        movie = self._managed_movie(selected)
        added = False
        if movie is None:
            if not self.settings.request_defaults_ready("radarr"):
                raise ConfigurationError(self._im("request_defaults_missing"))
            tmdb_id = _unique_id(selected, "tmdb")
            term = f"tmdb:{tmdb_id}" if tmdb_id else f"{selected.title} {selected.year or ''}".strip()
            candidate = dict(self._pick_lookup(self.radarr.lookup_movie(term), selected, "tmdbId", tmdb_id))
            movie = self._managed_movie(selected)
            if movie is None:
                candidate.update({
                    "qualityProfileId": self.settings.request_radarr_profile,
                    "rootFolderPath": self.settings.request_radarr_root,
                    "monitored": True,
                    "addOptions": {"searchForMovie": False},
                })
                self.radarr.add_movie(candidate)
                added = True
                movie = self._managed_movie(selected)
                if movie is None:
                    raise SafetyError(self._im("movie_reresolve_failed"))
        if not movie.get("monitored"):
            updated = dict(movie)
            updated["monitored"] = True
            movie = self.radarr.update_movie(updated)
        try:
            self._poll_command(self.radarr, self.radarr.search_movie(movie["id"]), "Radarr movie search")
        except Exception as exc:
            if added:
                raise SafetyError(self._im("request_partial", title=movie.get("title") or selected.display_name)) from exc
            raise
        if added:
            return self._im("request_movie_done", title=movie.get("title") or selected.display_name)
        return self._im("request_existing_done")

    def _request_series_or_episode(self, selected):
        series = self._managed_series(selected)
        added = False
        if series is None:
            if not self.settings.request_defaults_ready("sonarr"):
                raise ConfigurationError(self._im("request_defaults_missing"))
            tvdb_id = _series_tvdb_id(selected)
            title = selected.tvshow_title or selected.title
            year = _series_year(selected)
            term = f"tvdb:{tvdb_id}" if tvdb_id else f"{title} {year or ''}".strip()
            candidate = dict(self._pick_lookup(
                self.sonarr.lookup_series(term), selected, "tvdbId", tvdb_id,
                match_title=title, match_year=year,
            ))
            series = self._managed_series(selected)
            if series is None:
                monitor = "none" if selected.media_type == "episode" else self.settings.request_sonarr_monitor
                candidate.update({
                    "qualityProfileId": self.settings.request_sonarr_profile,
                    "rootFolderPath": self.settings.request_sonarr_root,
                    "monitored": selected.media_type != "episode",
                    "seasonFolder": True,
                    "addOptions": {
                        "monitor": monitor,
                        "searchForMissingEpisodes": False,
                        "searchForCutoffUnmetEpisodes": False,
                    },
                })
                self.sonarr.add_series(candidate)
                added = True
                series = self._managed_series(selected)
                if series is None:
                    raise SafetyError(self._im("series_reresolve_failed"))

        try:
            if selected.media_type == "episode":
                episode = resolve_episode(selected, self.sonarr, series)
                if not episode.get("monitored"):
                    self.sonarr.set_episodes_monitored([episode["id"]], True)
                self._poll_command(self.sonarr, self.sonarr.search_episodes([episode["id"]]), "Sonarr episode search")
                return self._im(
                    "request_episode_done", title=series.get("title") or selected.tvshow_title,
                    season=selected.season, episode=selected.episode,
                )
            if not series.get("monitored"):
                updated = dict(series)
                updated["monitored"] = True
                series = self.sonarr.update_series(updated)
            self._poll_command(self.sonarr, self.sonarr.search_series(series["id"]), "Sonarr series search")
        except Exception as exc:
            if added:
                raise SafetyError(self._im("request_partial", title=series.get("title") or selected.display_name)) from exc
            raise
        if added:
            return self._im("request_series_done", title=series.get("title") or selected.display_name)
        return self._im("request_existing_done")

    def interactive_search(self, selected):
        if selected.media_type == "movie":
            entity = self._managed_movie(selected)
            if not entity:
                raise ResolutionError(self._im("movie_not_managed"))
            client, service = self.radarr, "Radarr"
            rows = client.releases(entity["id"])
        elif selected.media_type == "episode":
            series = self._managed_series(selected)
            if not series:
                raise ResolutionError(self._im("series_not_managed"))
            episode = resolve_episode(selected, self.sonarr, series)
            client, service = self.sonarr, "Sonarr"
            rows = client.releases(episode["id"])
        else:
            self.ui.ok(self._im("interactive_search"), self._im("series_interactive_unsupported"))
            return self._im("series_interactive_unsupported")

        if not rows:
            self._show_prowlarr_information(selected)
            self.ui.ok(self._im("interactive_search"), self._im("release_none"))
            return self._im("release_none")
        labels = [self._release_summary(row) for row in rows]
        choice = self.ui.select(self._im("release_choose"), labels)
        if choice < 0:
            return self._m("cancelled")
        picked = rows[choice]
        details = self._release_details(picked)
        self.ui.text(self._im("release_details"), details)
        if not self.ui.confirm(self._im("interactive_search"), self._im("release_confirm", service=service, details=details)):
            return self._m("cancelled")
        target_id = entity["id"] if selected.media_type == "movie" else episode["id"]
        fresh_rows = client.releases(target_id)
        matches = [row for row in fresh_rows if _release_key(row) == _release_key(picked)]
        if len(matches) != 1:
            raise SafetyError(self._im("release_stale"))
        client.download_release(matches[0])
        result = self._im("release_grabbed", service=service)
        self.ui.notification(result)
        return result

    def _show_prowlarr_information(self, selected):
        if not self.settings.prowlarr.enabled:
            return
        try:
            query = selected.tvshow_title or selected.title
            count = len(self.prowlarr.search(query))
            if count:
                self.ui.ok(self._im("interactive_search"), self._im("prowlarr_info", count=count))
        except Exception as exc:
            if self.logger:
                self.logger.debug("Prowlarr supplementary search failed: %s", type(exc).__name__)

    def _release_summary(self, row):
        quality = row.get("quality") or {}
        if isinstance(quality, dict):
            nested = quality.get("quality") or quality
            quality = nested.get("name", "?") if isinstance(nested, dict) else "?"
        rejected = row.get("rejections") or []
        state = self._im("release_state_rejected") if rejected or row.get("rejected") else self._im("release_state_accepted")
        size_gib = float(row.get("size") or 0) / (1024 ** 3)
        peers = row.get("seeders") if row.get("seeders") is not None else row.get("peers")
        return (
            f"[{state}] {quality} - {size_gib:.2f} GiB - "
            f"{row.get('indexer') or '?'} - {peers if peers is not None else '?'} peers\n"
            f"{row.get('title') or '?'}"
        )

    def _release_details(self, row):
        rejected = row.get("rejections") or []
        return self._im(
            "release_detail_template", title=str(row.get("title") or "?"),
            indexer=str(row.get("indexer") or "?"), protocol=str(row.get("protocol") or "?"),
            age=row.get("age") if row.get("age") is not None else "?",
            score=row.get("customFormatScore") if row.get("customFormatScore") is not None else "?",
            rejections=", ".join(str(value) for value in rejected) if rejected else self._im("release_rejections_none"),
        )

    def dashboard(self, _selected=None):
        lines = []
        services = [
            ("Radarr", self.settings.radarr, lambda: self._servarr_dashboard(self.radarr, "movies")),
            ("Sonarr", self.settings.sonarr, lambda: self._servarr_dashboard(self.sonarr, "episodes")),
            ("Prowlarr", self.settings.prowlarr, self._prowlarr_dashboard),
            ("Bazarr", self.settings.bazarr, self._bazarr_dashboard),
        ]
        for name, config, loader in services:
            if not config.enabled:
                lines.append(self._im("dashboard_line", service=name, detail=self._im("optional_disabled")))
                continue
            try:
                detail = loader()
            except Exception as exc:
                detail = self._im("service_unavailable", error_type=type(exc).__name__)
            lines.append(self._im("dashboard_line", service=name, detail=detail))
        text = "\n".join(lines)
        self.ui.text(self._im("dashboard_title"), text)
        return text

    @staticmethod
    def _queue_counts(queue):
        records = queue.get("records") if isinstance(queue, dict) else []
        records = records if isinstance(records, list) else []
        total = _positive_id(queue.get("totalRecords")) if isinstance(queue, dict) else 0
        total = total or len(records)
        problem_states = {"failed", "warning", "delay", "downloadwarning"}
        problems = sum(1 for row in records if str(row.get("status") or "").lower() in problem_states)
        return total, problems

    def _servarr_dashboard(self, client, wanted_label):
        status = client.status()
        health = client.health()
        wanted = client.wanted_missing()
        queue_total, queue_problems = self._queue_counts(client.queue_overview())
        missing = _positive_id(wanted.get("totalRecords")) or len(wanted.get("records") or [])
        return f"{status.get('version') or '?'} - health {len(health)} - queue {queue_total} ({queue_problems} problem) - missing {missing} {wanted_label}"

    def _prowlarr_dashboard(self):
        status = self.prowlarr.status()
        health = self.prowlarr.health()
        indexers = self.prowlarr.indexers()
        enabled = sum(1 for row in indexers if row.get("enable") or row.get("enableRss") or row.get("enableAutomaticSearch"))
        return f"{status.get('version') or '?'} - health {len(health)} - enabled indexers {enabled}/{len(indexers)}"

    def _bazarr_dashboard(self):
        status = self.bazarr.status()
        data = status.get("data") if isinstance(status.get("data"), dict) else status
        return str(data.get("version") or data.get("bazarr_version") or "connected")

    def configure_request_defaults(self, _selected=None):
        configured = 0
        services = (
            ("Radarr", self.settings.radarr, lambda: self.radarr),
            ("Sonarr", self.settings.sonarr, lambda: self.sonarr),
        )
        for service, config, loader in services:
            if not config.enabled:
                continue
            client = loader()
            roots = client.root_folders()
            profiles = client.quality_profiles()
            if not roots or not profiles:
                raise ConfigurationError(self._im("defaults_missing_choices", service=service))
            root_choice = 0 if len(roots) == 1 else self.ui.select(
                self._im("choose_root", service=service), [str(row.get("path") or row.get("name") or "?") for row in roots],
            )
            if root_choice < 0:
                return self._m("cancelled")
            profile_choice = 0 if len(profiles) == 1 else self.ui.select(
                self._im("choose_profile", service=service), [str(row.get("name") or row.get("id") or "?") for row in profiles],
            )
            if profile_choice < 0:
                return self._m("cancelled")
            prefix = service.lower()
            self.settings.addon.setSetting(f"request_{prefix}_root", str(roots[root_choice].get("path") or ""))
            self.settings.addon.setSetting(f"request_{prefix}_profile", str(_positive_id(profiles[profile_choice].get("id"))))
            configured += 1
        if not configured:
            raise ConfigurationError(self._im("defaults_no_services"))
        result = self._im("defaults_saved")
        self.ui.notification(result)
        return result

    def configure_subtitle_languages(self, _selected=None):
        if not self.settings.bazarr.enabled:
            raise ConfigurationError(self._im("bazarr_disabled"))
        rows = self.bazarr.languages()
        choices = []
        for row in rows:
            code = str(row.get("code2") or row.get("code3") or row.get("code") or "").strip().lower()
            if not code or any(code == existing[0] for existing in choices):
                continue
            name = str(row.get("name") or row.get("language") or code)
            choices.append((code, name))
        if not choices:
            raise ApiError(self._im("bazarr_no_languages"))
        selected_codes = []
        labels = [self._im("languages_none")] + [f"{name} ({code})" for code, name in choices]
        for slot in range(1, 4):
            choice = self.ui.select(self._im("languages_choose_slot", slot=slot), labels)
            if choice <= 0:
                break
            code = choices[choice - 1][0]
            if code in selected_codes:
                continue
            selected_codes.append(code)
        for index in range(3):
            value = selected_codes[index] if index < len(selected_codes) else ""
            self.settings.addon.setSetting(f"bazarr_language_{index + 1}", value)
        result = self._im("languages_saved", count=len(selected_codes))
        self.ui.notification(result)
        return result

    def find_subtitles(self, _selected=None):
        try:
            import xbmc
            player = xbmc.Player()
            if not player.isPlayingVideo():
                self.ui.notification(self._im("find_subtitles_playback"), error=True)
                return self._im("find_subtitles_playback")
            xbmc.executebuiltin("ActivateWindow(subtitlesearch)")
            return self._im("find_subtitles")
        except Exception as exc:
            raise SafetyError(self._im("find_subtitles_window_failed")) from exc
