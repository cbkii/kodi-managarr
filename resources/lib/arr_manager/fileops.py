from urllib.parse import urlsplit

from .errors import ConfigurationError, SafetyError
from .util import is_path_under, is_sftp_network_url, normalise_path


class FileBackend:
    name = "base"

    def delete_file(self, path):
        raise NotImplementedError

    def delete_tree(self, path):
        raise NotImplementedError

    def close(self):
        return None


class KodiNetworkVFSBackend(FileBackend):
    name = "Kodi VFS (SMB/SFTP)"

    def __init__(self, protected_paths=None, logger=None):
        import xbmcvfs
        self.vfs = xbmcvfs
        self.protected_paths = protected_paths or []
        self.logger = logger
        self._sftp_checked = False

    def exists(self, path):
        self._check(path, folder=False)
        return bool(self.vfs.exists(path))

    def delete_file(self, path):
        self._check(path, folder=False)
        if self.vfs.exists(path) and not self.vfs.delete(path):
            raise SafetyError(f"Kodi VFS could not delete {path}")

    def delete_tree(self, path):
        self._check(path, folder=True)
        if not self.vfs.exists(path):
            return
        self._walk_delete(path)

    def _walk_delete(self, path):
        try:
            dirs, files = self.vfs.listdir(path)
        except Exception as exc:
            raise SafetyError(f"Kodi VFS could not enumerate folder {path}; refusing recursive deletion") from exc
        if dirs is None or files is None:
            raise SafetyError(f"Kodi VFS could not enumerate folder {path}; refusing recursive deletion")
        for filename in files:
            child = path.rstrip("/") + "/" + filename
            if not self.vfs.delete(child):
                raise SafetyError(f"Kodi VFS could not delete {child}")
        for dirname in dirs:
            self._walk_delete(path.rstrip("/") + "/" + dirname)
        try:
            ok = self.vfs.rmdir(path, force=False)
        except TypeError:
            ok = self.vfs.rmdir(path)
        if not ok and self.vfs.exists(path):
            raise SafetyError(f"Kodi VFS could not remove folder {path}")

    def _check(self, path, folder):
        _validate_delete_path(path, self.protected_paths, folder)
        if is_sftp_network_url(path):
            self._ensure_sftp_addon()

    def _ensure_sftp_addon(self):
        if self._sftp_checked:
            return
        try:
            import xbmc
            if not xbmc.getCondVisibility("System.HasAddon(vfs.sftp)"):
                raise ConfigurationError(_SFTP_ADDON_MESSAGE)
        except ImportError as exc:
            raise ConfigurationError(_SFTP_ADDON_MESSAGE) from exc
        self._sftp_checked = True


# Backwards-compatible import name for older tests or add-on state. New code should use KodiNetworkVFSBackend.
KodiVFSBackend = KodiNetworkVFSBackend


_SFTP_ADDON_MESSAGE = (
    "Kodi SFTP support (vfs.sftp) is not installed or enabled. Install 'SFTP support' from Kodi's add-on "
    "repository, then create and verify an SSH/SFTP network location in Kodi before testing deletion. The binary "
    "add-on must match your Kodi major version."
)
_NETWORK_SCHEMES = {"smb", "sftp", "ssh"}
_SFTP_SCHEMES = {"sftp", "ssh"}


def _network_root_message(scheme):
    if scheme == "smb":
        return "Refusing to recursively remove an SMB share root"
    return "Refusing to delete an SFTP/SSH server root or top-level remote directory"


def _validate_delete_path(path, protected_paths, folder):
    raw_parts = urlsplit((path or "").strip())
    if raw_parts.scheme.lower() in _NETWORK_SCHEMES and (raw_parts.username or raw_parts.password):
        raise SafetyError("Refusing to delete credential-bearing network URLs; use Kodi-saved credentials instead")
    normal = normalise_path(path)
    if not normal or normal in {"/", "~", ".", ".."}:
        raise SafetyError("Refusing to delete an empty, home, current, parent, or root path")
    if normal.startswith("~/") or normal.startswith("../") or normal == "..":
        raise SafetyError("Refusing to delete a home-relative or parent-relative path")

    parts = urlsplit(normal)
    scheme = parts.scheme.lower()
    if scheme in _NETWORK_SCHEMES:
        _validate_network_delete_path(parts, folder)
    elif "://" in normal:
        raise SafetyError("Refusing to delete a malformed or unsupported network path")
    elif folder and len([part for part in normal.split("/") if part]) < 2:
        raise SafetyError("Refusing to recursively remove a top-level filesystem path")

    for protected in protected_paths or []:
        if _is_protected_delete_target(normal, protected):
            raise SafetyError(f"Refusing to delete protected path {normal}")


def _validate_network_delete_path(parts, folder):
    if not parts.hostname:
        raise SafetyError("Refusing to delete a malformed or credential-only network URL")
    if parts.path in {"", "/"}:
        raise SafetyError(_network_root_message(parts.scheme.lower()))

    segments = [segment for segment in parts.path.split("/") if segment]
    if any(segment in {".", "..", "~"} for segment in segments):
        raise SafetyError("Refusing to delete a network path containing current, parent, or home segments")
    if parts.scheme.lower() == "smb":
        if folder and len(segments) < 2:
            raise SafetyError(_network_root_message("smb"))
    else:
        # sftp://host/media or sftp://host:22/media names a remote top-level directory; require an item below it.
        if folder and len(segments) < 2:
            raise SafetyError(_network_root_message(parts.scheme.lower()))


def _is_protected_delete_target(target, protected):
    target_sftp = _canonical_sftp_path(target)
    protected_sftp = _canonical_sftp_path(protected)
    if target_sftp and protected_sftp:
        return _canonical_path_under(target_sftp, protected_sftp) or _canonical_path_under(protected_sftp, target_sftp)
    return normalise_path(target).casefold() == normalise_path(protected).casefold() or is_path_under(protected, target)


def _canonical_sftp_path(value):
    parts = urlsplit(normalise_path(value))
    if parts.scheme.lower() not in _SFTP_SCHEMES or not parts.hostname:
        return None
    try:
        port = parts.port
    except ValueError as exc:
        raise SafetyError("Refusing to delete a malformed SFTP/SSH URL") from exc
    if port == 22:
        port = None
    return ("sftp", parts.hostname.lower(), port, (parts.path or "/").rstrip("/") or "/")


def _canonical_path_under(path, parent):
    path_scheme, path_host, path_port, path_value = path
    parent_scheme, parent_host, parent_port, parent_value = parent
    if (path_scheme, path_host, path_port) != (parent_scheme, parent_host, parent_port):
        return False
    return path_value == parent_value or path_value.startswith(parent_value.rstrip("/") + "/")


def make_direct_backend(settings, logger=None):
    settings.validate_backend()
    if settings.backend == "vfs":
        return KodiNetworkVFSBackend(settings.protected_paths, logger)
    return None
