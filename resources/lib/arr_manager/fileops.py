import os
import posixpath
import stat
import time

from .errors import ConfigurationError, SafetyError
from .util import is_path_under, normalise_path, sha256_fingerprint


class FileBackend:
    name = "base"

    def delete_file(self, path):
        raise NotImplementedError

    def delete_tree(self, path):
        raise NotImplementedError

    def close(self):
        return None


class KodiVFSBackend(FileBackend):
    name = "Kodi SMB/VFS"

    def __init__(self, protected_paths=None, logger=None):
        import xbmcvfs
        self.vfs = xbmcvfs
        self.protected_paths = protected_paths or []
        self.logger = logger

    def exists(self, path):
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
        dirs, files = self.vfs.listdir(path)
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


class SSHSFTPBackend(FileBackend):
    name = "SSH/SFTP"

    def __init__(self, config, protected_paths=None, logger=None):
        try:
            import paramiko
        except ImportError as exc:
            raise ConfigurationError(
                "The optional Python 'paramiko' module is not installed in Kodi. Use Servarr API or Kodi SMB/VFS, "
                "or install a Kodi-compatible Paramiko module."
            ) from exc
        self.paramiko = paramiko
        self.config = config
        self.protected_paths = protected_paths or []
        self.logger = logger
        self.client = None
        self.sftp = None
        self._connect()

    def _connect(self):
        cfg = self.config
        client = self.paramiko.SSHClient()
        try:
            client.load_system_host_keys()
        except OSError:
            pass

        outer = self
        class PinPolicy(self.paramiko.MissingHostKeyPolicy):
            def missing_host_key(self, client_obj, hostname, key):
                fingerprint = sha256_fingerprint(key.asbytes())
                configured = (cfg.host_key_sha256 or "").strip()
                if configured and fingerprint == configured:
                    client_obj.get_host_keys().add(hostname, key.get_name(), key)
                    return
                if cfg.allow_unknown_host_key:
                    client_obj.get_host_keys().add(hostname, key.get_name(), key)
                    if outer.logger:
                        outer.logger.warning("Trusting unknown SSH host key %s", fingerprint)
                    return
                raise SafetyError(
                    f"SSH host key is not trusted. Set SSH host-key fingerprint to {fingerprint} in add-on settings."
                )

        client.set_missing_host_key_policy(PinPolicy())
        kwargs = {
            "hostname": cfg.host,
            "port": cfg.port,
            "username": cfg.username,
            "timeout": 15,
            "banner_timeout": 15,
            "auth_timeout": 15,
            "look_for_keys": False,
            "allow_agent": False,
        }
        if cfg.key_path:
            key_path = cfg.key_path
            if key_path.startswith("special://"):
                try:
                    import xbmcvfs
                    key_path = xbmcvfs.translatePath(key_path)
                except Exception:
                    pass
            kwargs["key_filename"] = key_path
        if cfg.password:
            kwargs["password"] = cfg.password
        client.connect(**kwargs)
        self.client = client
        self.sftp = client.open_sftp()

    def delete_file(self, path):
        self._check(path, folder=False)
        try:
            self.sftp.remove(path)
        except FileNotFoundError:
            return

    def delete_tree(self, path):
        self._check(path, folder=True)
        self._walk_delete(path)

    def _walk_delete(self, path):
        try:
            entries = self.sftp.listdir_attr(path)
        except FileNotFoundError:
            return
        for entry in entries:
            child = posixpath.join(path, entry.filename)
            if stat.S_ISDIR(entry.st_mode):
                self._walk_delete(child)
            else:
                self.sftp.remove(child)
        self.sftp.rmdir(path)

    def _check(self, path, folder):
        _validate_delete_path(path, self.protected_paths, folder)

    def close(self):
        try:
            if self.sftp:
                self.sftp.close()
        finally:
            if self.client:
                self.client.close()


def _validate_delete_path(path, protected_paths, folder):
    normal = normalise_path(path)
    if not normal or normal in {"/", ".", ".."}:
        raise SafetyError("Refusing to delete an empty or root path")
    for protected in protected_paths or []:
        if normalise_path(normal).casefold() == normalise_path(protected).casefold() or is_path_under(protected, normal):
            raise SafetyError(f"Refusing to delete protected path {normal}")
    if normal.startswith("smb://"):
        # smb://host/share is a share root; require an item below it for folder removal.
        pieces = normal.split("/", 4)
        if folder and len(pieces) < 5:
            raise SafetyError("Refusing to recursively remove an SMB share root")
    elif folder and len([part for part in normal.split("/") if part]) < 2:
        raise SafetyError("Refusing to recursively remove a top-level filesystem path")


def make_direct_backend(settings, logger=None):
    settings.validate_backend()
    if settings.backend == "vfs":
        return KodiVFSBackend(settings.protected_paths, logger)
    if settings.backend == "ssh":
        return SSHSFTPBackend(settings.ssh, settings.protected_paths, logger)
    return None
