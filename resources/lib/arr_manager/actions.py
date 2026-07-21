# SPDX-License-Identifier: GPL-3.0-or-later
from .actions_destructive import DestructiveMixin
from .actions_management import ManagementMixin
from .actions_shared import SharedSafetyMixin
from .clients import RadarrClient, SonarrClient
from .errors import ResolutionError
from .messages import message


class ArrManager(ManagementMixin, DestructiveMixin, SharedSafetyMixin):
    def __init__(self, settings, ui, logger):
        self.settings = settings
        self.ui = ui
        self.logger = logger
        self._radarr = None
        self._sonarr = None

    def _m(self, key, **values):
        return message(self.ui, key, **values)

    @property
    def radarr(self):
        if self._radarr is None:
            cfg = self.settings.radarr
            cfg.validate("Radarr")
            self._radarr = RadarrClient(
                cfg.url,
                cfg.api_key,
                cfg.api_version,
                cfg.timeout,
                cfg.verify_tls,
                self.logger,
                cfg.user_agent,
            )
        return self._radarr

    @property
    def sonarr(self):
        if self._sonarr is None:
            cfg = self.settings.sonarr
            cfg.validate("Sonarr")
            self._sonarr = SonarrClient(
                cfg.url,
                cfg.api_key,
                cfg.api_version,
                cfg.timeout,
                cfg.verify_tls,
                self.logger,
                cfg.user_agent,
            )
        return self._sonarr

    def execute(self, action, selected, **kwargs):
        if selected.media_type not in {"movie", "tvshow", "episode"}:
            raise ResolutionError(f"Unsupported Kodi item type: {selected.media_type or 'unknown'}")
        self.settings.validate_backend()
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
        }
        if action not in handlers:
            raise ResolutionError(f"Unknown action: {action}")
        return handlers[action](selected)
