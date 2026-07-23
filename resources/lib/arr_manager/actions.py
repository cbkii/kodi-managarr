# SPDX-License-Identifier: GPL-3.0-or-later
from .actions_destructive import DestructiveMixin
from .actions_interactive import InteractiveMixin
from .actions_management import ManagementMixin
from .actions_shared import SharedSafetyMixin
from .bazarr_client import BazarrClient
from .clients import ProwlarrClient, RadarrClient, SonarrClient
from .errors import ResolutionError
from .messages import message


class ArrManager(InteractiveMixin, ManagementMixin, DestructiveMixin, SharedSafetyMixin):
    def __init__(self, settings, ui, logger):
        self.settings = settings
        self.ui = ui
        self.logger = logger
        self._radarr = None
        self._sonarr = None
        self._prowlarr = None
        self._bazarr = None

    def _m(self, key, **values):
        return message(self.ui, key, **values)

    @property
    def radarr(self):
        if self._radarr is None:
            cfg = self.settings.radarr
            cfg.validate("Radarr")
            self._radarr = RadarrClient(cfg.url, cfg.api_key, cfg.api_version, cfg.timeout, cfg.verify_tls,
                                        self.logger, cfg.user_agent)
        return self._radarr

    @property
    def sonarr(self):
        if self._sonarr is None:
            cfg = self.settings.sonarr
            cfg.validate("Sonarr")
            self._sonarr = SonarrClient(cfg.url, cfg.api_key, cfg.api_version, cfg.timeout, cfg.verify_tls,
                                        self.logger, cfg.user_agent)
        return self._sonarr

    @property
    def prowlarr(self):
        if self._prowlarr is None:
            cfg = self.settings.prowlarr
            cfg.validate("Prowlarr")
            self._prowlarr = ProwlarrClient(cfg.url, cfg.api_key, cfg.api_version, cfg.timeout, cfg.verify_tls,
                                            self.logger, cfg.user_agent)
        return self._prowlarr

    @property
    def bazarr(self):
        if self._bazarr is None:
            cfg = self.settings.bazarr
            cfg.validate("Bazarr")
            self._bazarr = BazarrClient(cfg.url, cfg.api_key, cfg.timeout, cfg.verify_tls,
                                        self.logger, cfg.user_agent)
        return self._bazarr

    def execute(self, action, selected=None, **kwargs):
        handlers = {
            "delete_exclude": self.delete_exclude,
            "delete_replace": self.delete_replace,
            "status": self.status,
            "search_now": self.search_now,
            "monitor": lambda item: self.set_monitoring(item, True),
            "unmonitor": lambda item: self.set_monitoring(item, False),
            "change_quality_profile": lambda item: self.change_quality_profile(item, kwargs["profile_id"]),
            "queue_view": self.queue_entries,
            "queue_remove": lambda item: self.remove_queue_item(item, kwargs["queue_id"]),
            "request_search": self.request_search,
            "interactive_search": self.interactive_search,
            "dashboard": self.dashboard,
            "find_subtitles": self.find_subtitles,
            "configure_request_defaults": self.configure_request_defaults,
            "configure_subtitle_languages": self.configure_subtitle_languages,
        }
        if action not in handlers:
            raise ResolutionError(f"Unknown action: {action}")
        if selected is not None and selected.media_type not in {"movie", "tvshow", "episode"}:
            raise ResolutionError(f"Unsupported Kodi item type: {selected.media_type or 'unknown'}")
        if action in {"delete_exclude", "delete_replace", "status", "search_now", "monitor", "unmonitor",
                      "change_quality_profile", "queue_view", "queue_remove"}:
            self.settings.validate_backend()
        return handlers[action](selected)
