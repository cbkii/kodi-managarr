from dataclasses import dataclass

from .errors import ConfigurationError
from .util import PathMapper, as_bool, as_int, parse_mappings


BACKENDS = {"0": "api", "1": "vfs", "2": "ssh", "api": "api", "vfs": "vfs", "ssh": "ssh"}


@dataclass
class ServiceConfig:
    enabled: bool
    url: str
    api_key: str
    api_version: str
    timeout: int
    verify_tls: bool

    def validate(self, name):
        if not self.enabled:
            raise ConfigurationError(f"{name} is disabled in add-on settings")
        if not self.url:
            raise ConfigurationError(f"Set the {name} URL in add-on settings")
        if not self.api_key:
            raise ConfigurationError(f"Set the {name} API key in add-on settings")


@dataclass
class SSHConfig:
    enabled: bool
    host: str
    port: int
    username: str
    password: str
    key_path: str
    host_key_sha256: str
    allow_unknown_host_key: bool


class Settings:
    def __init__(self, addon):
        self.addon = addon
        get = addon.getSetting
        self.backend = BACKENDS.get(get("deletion_backend"), get("deletion_backend") or "api")
        self.confirm = as_bool(get("confirm_actions"), True)
        self.dry_run = as_bool(get("dry_run"), False)
        self.require_blocklist = as_bool(get("require_blocklist"), True)
        self.debug = as_bool(get("debug"), False)
        self.path_mapper = PathMapper(parse_mappings(get("path_mappings")))
        self.protected_paths = [x.strip() for x in get("protected_paths").replace("\n", ";").split(";") if x.strip()]
        self.poll_timeout = as_int(get("rescan_poll_timeout"), 45, 5, 300)

        timeout = as_int(get("http_timeout"), 15, 3, 120)
        self.radarr = ServiceConfig(
            enabled=as_bool(get("radarr_enabled"), True),
            url=get("radarr_url").strip(),
            api_key=get("radarr_api_key").strip(),
            api_version=get("radarr_api_version").strip() or "v3",
            timeout=timeout,
            verify_tls=as_bool(get("radarr_verify_tls"), True),
        )
        self.sonarr = ServiceConfig(
            enabled=as_bool(get("sonarr_enabled"), True),
            url=get("sonarr_url").strip(),
            api_key=get("sonarr_api_key").strip(),
            api_version=get("sonarr_api_version").strip() or "v3",
            timeout=timeout,
            verify_tls=as_bool(get("sonarr_verify_tls"), True),
        )
        self.ssh = SSHConfig(
            enabled=as_bool(get("ssh_enabled"), False),
            host=get("ssh_host").strip(),
            port=as_int(get("ssh_port"), 22, 1, 65535),
            username=get("ssh_username").strip(),
            password=get("ssh_password"),
            key_path=get("ssh_key_path").strip(),
            host_key_sha256=get("ssh_host_key_sha256").strip(),
            allow_unknown_host_key=as_bool(get("ssh_allow_unknown_host_key"), False),
        )

    def validate_backend(self):
        if self.backend not in {"api", "vfs", "ssh"}:
            raise ConfigurationError("Unknown deletion backend")
        if self.backend == "ssh":
            if not self.ssh.enabled:
                raise ConfigurationError("Enable SSH/SFTP in settings or choose another deletion backend")
            if not self.ssh.host or not self.ssh.username:
                raise ConfigurationError("SSH host and username are required")
