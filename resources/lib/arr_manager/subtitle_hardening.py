# SPDX-License-Identifier: GPL-3.0-or-later
"""Compatibility hardening for the Bazarr subtitle runtime boundary."""


def _flag(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _normalise_row(row):
    value = dict(row or {})
    for key in ("original_format", "forced", "hearing_impaired", "hi"):
        value[key] = _flag(value.get(key))
    return value


def install(module):
    """Patch the loaded subtitle module once, without changing its public surface."""
    if getattr(module, "_subtitle_hardening_installed", False):
        return

    original_select = module._select_results
    original_label = module._result_label
    original_safe_result = module._safe_result

    def select_results(rows, allowed_languages):
        normalised = [_normalise_row(row) for row in rows if isinstance(row, dict)]
        return original_select(normalised, allowed_languages)[:3]

    def result_label(addon, row, language):
        return original_label(addon, _normalise_row(row), language)

    def safe_result(row):
        return original_safe_result(_normalise_row(row))

    def selected_from_player(addon, xbmc_module, kodi_client):
        db_type = str(xbmc_module.getInfoLabel("VideoPlayer.DBTYPE") or "").strip().lower()
        db_id = module._positive_int(xbmc_module.getInfoLabel("VideoPlayer.DBID"), 0)
        playing_file = str(xbmc_module.Player().getPlayingFile() or "")
        if db_type == "movie" and db_id > 0:
            detail = kodi_client.movie_details(db_id)
            return module.SelectedItem(
                media_type="movie", db_id=db_id, title=str(detail.get("title") or ""),
                year=module._positive_int(detail.get("year"), 0),
                file_path=str(detail.get("file") or playing_file),
                unique_ids=dict(detail.get("uniqueid") or {}),
            )
        if db_type == "episode" and db_id > 0:
            detail = kodi_client.episode_details(db_id)
            tvshow_id = module._positive_int(detail.get("tvshowid"), 0)
            series_detail = {}
            if tvshow_id > 0:
                try:
                    series_detail = kodi_client.tvshow_details(tvshow_id)
                except module.KodiJsonRpcError:
                    series_detail = {}
            return module.SelectedItem(
                media_type="episode", db_id=db_id, title=str(detail.get("title") or ""),
                tvshow_title=str(
                    detail.get("showtitle") or detail.get("tvshowtitle")
                    or series_detail.get("title") or ""
                ),
                tvshow_db_id=tvshow_id,
                season=module._positive_int(detail.get("season"), -1),
                episode=module._positive_int(detail.get("episode"), -1),
                file_path=str(detail.get("file") or playing_file),
                unique_ids=dict(detail.get("uniqueid") or {}),
                series_year=module._positive_int(series_detail.get("year"), 0),
                series_unique_ids=dict(series_detail.get("uniqueid") or {}),
            )
        raise module.ResolutionError(module.imessage(addon, "subtitle_library_playback_required"))

    def download(self, token):
        payload = self._consume_cache(token)
        language = str(payload.get("language") or "").lower()
        if not module._language_allowed(language, self.settings.bazarr_languages):
            raise module.SafetyError(module.imessage(self.addon, "subtitle_invalid_request"))
        media_type, kodi_db_id, playing_file = self._current_playback()
        if media_type != payload.get("media_type") or kodi_db_id != module._positive_int(payload.get("kodi_db_id"), 0):
            raise module.SafetyError(module.imessage(self.addon, "subtitle_invalid_request"))
        before = set(self._subtitle_candidates(playing_file, language))
        result = payload.get("result")
        if payload.get("media_type") == "movie":
            response = self.manager.bazarr.download_movie_subtitle(payload.get("radarr_id"), language, result)
        elif payload.get("media_type") == "episode":
            response = self.manager.bazarr.download_episode_subtitle(
                payload.get("series_id"), payload.get("episode_id"), language, result,
            )
        else:
            raise module.SafetyError(module.imessage(self.addon, "subtitle_invalid_request"))

        response_path = self._response_path(response)
        if response_path:
            mapped = self._map_accessible_path(response_path)
            if mapped:
                return mapped
        deadline = module.time.monotonic() + 15
        last_candidates = before
        while module.time.monotonic() < deadline:
            candidates = set(self._subtitle_candidates(playing_file, language))
            last_candidates = candidates
            preferred = sorted(candidates - before) or sorted(candidates)
            if preferred:
                return preferred[-1]
            if self.ui.wait_for_abort(0.5):
                break
        if last_candidates:
            return sorted(last_candidates)[-1]
        if response_path:
            raise module.SafetyError("Bazarr created a subtitle path that Kodi cannot access")
        raise module.SafetyError(module.imessage(self.addon, "subtitle_not_found"))

    module._flag = _flag
    module._select_results = select_results
    module._result_label = result_label
    module._safe_result = safe_result
    module.selected_from_player = selected_from_player
    module.SubtitleService.download = download
    module._subtitle_hardening_installed = True
