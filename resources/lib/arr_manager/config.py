# SPDX-License-Identifier: GPL-3.0-or-later
import re
from dataclasses import dataclass

from .errors import ConfigurationError
from .registry import ACTION_REGISTRY
from .util import PathMapper, as_bool, as_int, normalise_path, parse_mappings

BACKENDS = {"0": "api", "1": "vfs", "api": "api", "vfs": "vfs", "ssh": "vfs", "2": "vfs"}
MENU_MODES = {"0": "0", "simple": "0", "1": "1", "advanced": "1"}
PIN_HASH_BYTES = 32
PIN_SALT_BYTES = 16
LANGUAGE_CODE_RE = re.compile(r"^[a-z0-9_-]{2,12}(?::(?:forced|hi))?$", re.I)
SONARR_MONITOR_MODES = {"all", "future", "missing", "existing", "firstSeason", "latestSeason", "pilot", "recent", "none"}


@dataclass
class ServiceConfig:
    enabled: bool
    url: str
    api_key: str
    api_version: str
    timeout: int
    verify_tls: bool
    user_agent: str = "Kodi-Managarr/unknown"

    def validate(self, name):
        if not self.enabled:
            raise ConfigurationError(f"{name} is disabled in add-on settings")
        if not self.url:
            raise ConfigurationError(f"Set the {name} URL in add-on settings")
        if not self.api_key:
            raise ConfigurationError(f"Set the {name} API key in add-on settings")


class Settings:
    def __init__(self, addon):
        self.addon = addon
        get = addon.getSetting
        self.backend = BACKENDS.get(get("deletion_backend"), get("deletion_backend") or "api")
        self.confirm = as_bool(get("confirm_actions"), True)
        self.dry_run = as_bool(get("dry_run"), False)
        self.require_blocklist = as_bool(get("require_blocklist"), True)
        self.debug = as_bool(get("debug"), False)

        self.menu_mode = MENU_MODES.get((get("menu_mode") or "").strip().lower(), "1")
        known_ids = {action["id"] for action in ACTION_REGISTRY}
        self.hidden_actions = self._known_action_ids(get("hidden_actions"), known_ids)
        self.action_order = self._known_action_ids(get("action_order"), known_ids)

        self.pin_hash = b""
        self.pin_salt = b""
        self.pin_invalid = False
        pin_hash_hex = (get("pin_hash") or "").strip()
        pin_salt_hex = (get("pin_salt") or "").strip()
        if pin_hash_hex or pin_salt_hex:
            if not pin_hash_hex or not pin_salt_hex:
                self.pin_invalid = True
            else:
                try:
                    self.pin_hash = bytes.fromhex(pin_hash_hex)
                    self.pin_salt = bytes.fromhex(pin_salt_hex)
                except ValueError:
                    self.pin_invalid = True
                else:
                    if len(self.pin_hash) != PIN_HASH_BYTES or len(self.pin_salt) != PIN_SALT_BYTES:
                        self.pin_invalid = True
                        self.pin_hash = b""
                        self.pin_salt = b""
        self.pin_enabled = self.pin_invalid or bool(self.pin_hash and self.pin_salt)

        self.path_mapping_warning = ""
        raw_mappings = get("path_mappings")
        try:
            mappings = parse_mappings(raw_mappings)
        except ValueError as exc:
            if self.backend == "vfs":
                raise ConfigurationError(str(exc)) from exc
            mappings = []
            self.path_mapping_warning = str(exc)
        self.path_mapper = PathMapper(mappings)

        protected = []
        if self.backend == "vfs":
            for raw_path in get("protected_paths").replace("\n", ";").split(";"):
                raw_path = raw_path.strip()
                if not raw_path:
                    continue
                try:
                    protected.append(normalise_path(raw_path))
                except ValueError as exc:
                    raise ConfigurationError(f"Invalid protected path: {exc}") from exc
            for root in self.path_mapper.kodi_roots:
                if root not in protected:
                    protected.append(root)
        self.protected_paths = protected

        self.poll_timeout = as_int(get("rescan_poll_timeout"), 45, 5, 300)
        timeout = as_int(get("http_timeout"), 15, 3, 120)
        try:
            version = addon.getAddonInfo("version") or "unknown"
        except Exception:
            version = "unknown"
        user_agent = f"Kodi-Managarr/{version}"
        self.radarr = self._service(get, "radarr", "v3", timeout, user_agent, True)
        self.sonarr = self._service(get, "sonarr", "v3", timeout, user_agent, True)
        self.prowlarr = self._service(get, "prowlarr", "v1", timeout, user_agent, False)
        self.bazarr = self._service(get, "bazarr", "v1", timeout, user_agent, False)

        self.request_radarr_root = (get("request_radarr_root") or "").strip()
        self.request_radarr_profile = as_int(get("request_radarr_profile"), 0, 0)
        self.request_sonarr_root = (get("request_sonarr_root") or "").strip()
        self.request_sonarr_profile = as_int(get("request_sonarr_profile"), 0, 0)
        monitor_mode = (get("request_sonarr_monitor") or "future").strip()
        self.request_sonarr_monitor = monitor_mode if monitor_mode in SONARR_MONITOR_MODES else "future"

        languages = []
        for key in ("bazarr_language_1", "bazarr_language_2", "bazarr_language_3"):
            value = (get(key) or "").strip().lower()
            if value and LANGUAGE_CODE_RE.fullmatch(value) and value not in languages:
                languages.append(value)
        self.bazarr_languages = languages

    @staticmethod
    def _service(get, prefix, default_version, timeout, user_agent, enabled_default):
        return ServiceConfig(
            enabled=as_bool(get(f"{prefix}_enabled"), enabled_default),
            url=(get(f"{prefix}_url") or "").strip(),
            api_key=(get(f"{prefix}_api_key") or "").strip(),
            api_version=(get(f"{prefix}_api_version") or default_version).strip(),
            timeout=timeout,
            verify_tls=as_bool(get(f"{prefix}_verify_tls"), True),
            user_agent=user_agent,
        )

    @staticmethod
    def _known_action_ids(raw, known_ids):
        result = []
        for value in (raw or "").split(","):
            value = value.strip()
            if value in known_ids and value not in result:
                result.append(value)
        return result

    def request_defaults_ready(self, service):
        if service == "radarr":
            return bool(self.request_radarr_root and self.request_radarr_profile > 0)
        if service == "sonarr":
            return bool(self.request_sonarr_root and self.request_sonarr_profile > 0)
        return False

    def validate_backend(self):
        if self.backend not in {"api", "vfs"}:
            raise ConfigurationError("Unknown deletion backend")
