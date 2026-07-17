# SPDX-License-Identifier: GPL-3.0-or-later
import json
import os

from .kodi_jsonrpc import KodiJsonRpcClient, KodiJsonRpcError
from .kodi_selected import (
    _movie_has_strong_identity, _movie_matches, _same_path,
    _tvshow_has_strong_identity, _tvshow_matches,
)
from .messages import message
from .util import normalise_title


class KodiUI:
    def __init__(self, addon):
        import xbmc
        import xbmcgui
        self.xbmc = xbmc
        self.xbmcgui = xbmcgui
        self.addon = addon
        self.name = addon.getAddonInfo("name")
        self.jsonrpc = KodiJsonRpcClient(xbmc)

    def localize(self, key, **values):
        return message(self.addon, key, **values)

    def notification(self, message, error=False, milliseconds=5000):
        icon = self.xbmcgui.NOTIFICATION_ERROR if error else self.xbmcgui.NOTIFICATION_INFO
        self.xbmcgui.Dialog().notification(self.name, message, icon, milliseconds)

    def ok(self, heading, message):
        return self.xbmcgui.Dialog().ok(heading, message)

    def text(self, heading, message):
        dialog = self.xbmcgui.Dialog()
        if hasattr(dialog, "textviewer"):
            return dialog.textviewer(heading, message, usemono=False)
        return dialog.ok(heading, message)

    def confirm(self, heading, prompt):
        return self.xbmcgui.Dialog().yesno(
            heading,
            prompt,
            yeslabel=self.localize("continue"),
            nolabel=self.localize("cancel"),
        )

    def select(self, heading, options):
        return self.xbmcgui.Dialog().select(heading, options)

    def progress(self, heading, message=""):
        dialog = self.xbmcgui.DialogProgress()
        dialog.create(heading, message)
        return dialog

    def open_settings(self):
        self.addon.openSettings()

    def record_transaction(self, transaction, exc=None):
        try:
            import time
            import xbmcvfs
            profile = xbmcvfs.translatePath(self.addon.getAddonInfo("profile"))
            os.makedirs(profile, exist_ok=True)
            payload = transaction.as_dict(exc)
            payload["generatedAt"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            temporary = os.path.join(profile, "last-transaction.json.tmp")
            target = os.path.join(profile, "last-transaction.json")
            with open(temporary, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2, sort_keys=True)
            os.replace(temporary, target)
        except Exception:
            self.xbmc.log("[Managarr] Could not write non-secret transaction state", self.xbmc.LOGDEBUG)

    def refresh_kodi_library(self):
        raise KodiJsonRpcError("Targeted Kodi JSON-RPC synchronisation requires workflow context")

    def plan_deleted_movie(self, selected):
        movie_id = self._resolve_movie_id(selected)
        if movie_id is None:
            return {"status": "already_absent", "kind": "movie"}
        return {"status": "planned", "kind": "movie", "id": movie_id}

    def plan_deleted_series(self, selected):
        tvshow_id = self._resolve_tvshow_id(selected)
        if tvshow_id is None:
            return {"status": "already_absent", "kind": "tvshow"}
        return {"status": "planned", "kind": "tvshow", "id": tvshow_id}

    def plan_deleted_episodes(self, selected, linked=None, file_paths=None):
        linked = list(linked or [])
        target_paths = [path for path in (file_paths or []) if path]
        if getattr(selected, "file_path", ""):
            target_paths.append(selected.file_path)
        episode_ids = []
        tvshow_id = 0
        if selected.media_type == "episode" and int(getattr(selected, "db_id", 0) or 0) > 0:
            try:
                detail = self.jsonrpc.episode_details(selected.db_id)
            except KodiJsonRpcError:
                detail = None
            if detail and self._episode_matches_selected(detail, selected):
                episode_ids.append(int(detail.get("episodeid") or selected.db_id))
                tvshow_id = int(detail.get("tvshowid") or 0)
        if selected.media_type == "tvshow" and int(getattr(selected, "db_id", 0) or 0) > 0:
            tvshow_id = self._resolve_tvshow_id(selected) or 0
        if not tvshow_id:
            tvshow_id = self._resolve_tvshow_id(selected, allow_absent=False) or 0
        target_numbers = {
            (int(item.get("seasonNumber", -999)), int(item.get("episodeNumber", -999)))
            for item in linked if isinstance(item, dict)
        }
        candidates = self.jsonrpc.episodes(tvshow_id)
        matched_numbers = set()
        for episode in candidates:
            episode_id = int(episode.get("episodeid") or 0)
            number = (int(episode.get("season", -999)), int(episode.get("episode", -999)))
            path_match = bool(target_paths) and any(_same_path(episode.get("file", ""), path) for path in target_paths)
            number_match = number in target_numbers
            if episode_id > 0 and (path_match or number_match):
                if episode_id not in episode_ids:
                    episode_ids.append(episode_id)
                if number_match:
                    matched_numbers.add(number)
        if not episode_ids:
            return {"status": "already_absent", "kind": "episodes", "targets": sorted(target_numbers)}
        return {
            "status": "planned",
            "kind": "episodes",
            "ids": episode_ids,
            "already_absent": sorted(target_numbers - matched_numbers),
        }

    def apply_sync_plan(self, plan):
        if not isinstance(plan, dict):
            raise KodiJsonRpcError("Kodi synchronisation plan is malformed")
        if plan.get("status") == "already_absent":
            return plan
        if plan.get("status") != "planned":
            raise KodiJsonRpcError("Kodi synchronisation plan is not ready")
        kind = plan.get("kind")
        if kind == "movie":
            result = self.jsonrpc.remove_movie(int(plan["id"]))
            return {**plan, "status": "removed", "result": result}
        if kind == "tvshow":
            result = self.jsonrpc.remove_tvshow(int(plan["id"]))
            return {**plan, "status": "removed", "result": result}
        if kind == "episodes":
            results = [{"id": episode_id, "result": self.jsonrpc.remove_episode(episode_id)} for episode_id in plan.get("ids", [])]
            return {**plan, "status": "removed", "removed": results}
        raise KodiJsonRpcError("Kodi synchronisation plan has an unknown kind")

    def sync_deleted_movie(self, selected):
        return self.apply_sync_plan(self.plan_deleted_movie(selected))

    def sync_deleted_series(self, selected):
        return self.apply_sync_plan(self.plan_deleted_series(selected))

    def sync_deleted_episodes(self, selected, linked=None, file_paths=None):
        return self.apply_sync_plan(self.plan_deleted_episodes(selected, linked, file_paths))

    def _resolve_movie_id(self, selected):
        db_id = int(getattr(selected, "db_id", 0) or 0)
        if db_id > 0:
            try:
                details = self.jsonrpc.movie_details(db_id)
            except KodiJsonRpcError:
                details = None
            if details and _movie_matches(details, selected, require_strong=False):
                return int(details.get("movieid") or db_id)
        candidates = [item for item in self.jsonrpc.movies() if _movie_matches(item, selected, require_strong=True)]
        if len(candidates) > 1:
            raise KodiJsonRpcError("Multiple Kodi movie rows matched the deleted media")
        if candidates:
            return int(candidates[0].get("movieid") or 0)
        if _movie_has_strong_identity(selected):
            return None
        raise KodiJsonRpcError("Could not safely resolve the Kodi movie row for targeted cleanup")

    def _resolve_tvshow_id(self, selected, allow_absent=True):
        # Prefer the captured parent TV-show ID for episode selections
        tvshow_db_id = int(getattr(selected, "tvshow_db_id", 0) or 0) if selected.media_type == "episode" else 0
        db_id = int(getattr(selected, "db_id", 0) or 0) if selected.media_type == "tvshow" else 0
        lookup_id = tvshow_db_id or db_id
        if lookup_id > 0:
            try:
                details = self.jsonrpc.tvshow_details(lookup_id)
            except KodiJsonRpcError:
                details = None
            if details and _tvshow_matches(details, selected, require_strong=False):
                return int(details.get("tvshowid") or lookup_id)
        candidates = [item for item in self.jsonrpc.tvshows() if _tvshow_matches(item, selected, require_strong=True)]
        if len(candidates) > 1:
            raise KodiJsonRpcError("Multiple Kodi TV show rows matched the deleted media")
        if candidates:
            return int(candidates[0].get("tvshowid") or 0)
        if allow_absent and _tvshow_has_strong_identity(selected):
            return None
        raise KodiJsonRpcError("Could not safely resolve the Kodi TV show row for targeted cleanup")

    @staticmethod
    def _episode_matches_selected(details, selected):
        if int(details.get("season", -999)) != int(getattr(selected, "season", -998)):
            return False
        if int(details.get("episode", -999)) != int(getattr(selected, "episode", -998)):
            return False
        selected_show = normalise_title(getattr(selected, "tvshow_title", "") or getattr(selected, "title", ""))
        detail_show = normalise_title(details.get("tvshowtitle", ""))
        if selected_show and detail_show and selected_show != detail_show:
            return False
        selected_path = getattr(selected, "file_path", "")
        detail_path = details.get("file", "")
        if selected_path and detail_path and not _same_path(selected_path, detail_path):
            return False
        return True

    def wait_for_abort(self, seconds):
        return self.xbmc.Monitor().waitForAbort(float(seconds))
