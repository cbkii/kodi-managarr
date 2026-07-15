import os
import posixpath
import re
import unicodedata
from urllib.parse import urlsplit, urlunsplit

SUPPORTED_KODI_NETWORK_SCHEMES = {"smb", "sftp", "ssh"}
SFTP_NETWORK_SCHEMES = {"sftp", "ssh"}


def as_bool(value, default=False):
    if value is None or value == "":
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def as_int(value, default=0, minimum=None, maximum=None):
    try:
        result = int(str(value).strip())
    except (TypeError, ValueError):
        result = default
    if minimum is not None:
        result = max(minimum, result)
    if maximum is not None:
        result = min(maximum, result)
    return result


def normalise_title(value):
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"[^a-zA-Z0-9]+", " ", value).lower().strip()
    return re.sub(r"\s+", " ", value)


def normalise_release(value):
    value = os.path.basename((value or "").replace("\\", "/"))
    value = re.sub(r"\.(mkv|mp4|avi|mov|m4v|ts|wmv)$", "", value, flags=re.I)
    return normalise_title(value)


_ENCODED_SEPARATOR_RE = re.compile(r"%(?:2f|5c)", re.I)
_ENCODED_DOT_RE = re.compile(r"%(?:2e)", re.I)
_UNSUPPORTED_KODI_SCHEMES = {"videodb", "stack", "plugin", "special", "zip", "rar", "bluray", "dvd"}


def _has_encoded_traversal(value):
    return bool(_ENCODED_SEPARATOR_RE.search(value or "") or _ENCODED_DOT_RE.search(value or ""))


def normalise_path(value):
    value = (value or "").strip().replace("\\", "/")
    if _has_encoded_traversal(value):
        raise ValueError("Encoded separators or dot segments are not safe for destructive paths")
    parts = urlsplit(value)
    scheme = parts.scheme.lower()
    if scheme in _UNSUPPORTED_KODI_SCHEMES:
        raise ValueError(f"Unsupported Kodi path scheme: {scheme}")
    if scheme in SUPPORTED_KODI_NETWORK_SCHEMES:
        if not parts.netloc or not parts.hostname:
            raise ValueError("Network paths require a host")
        if scheme == "smb":
            segments = [segment for segment in parts.path.split("/") if segment]
            if not segments:
                raise ValueError("SMB paths require a share")
        path = re.sub(r"/+", "/", parts.path).rstrip("/")
        segments = [segment for segment in path.split("/") if segment]
        if any(segment in {".", "..", "~"} for segment in segments):
            raise ValueError("Path traversal segments are not safe")
        netloc = parts.netloc.rsplit("@", 1)[-1].lower()
        return urlunsplit((scheme, netloc, path, "", ""))
    if scheme and "://" in value:
        raise ValueError(f"Unsupported path scheme: {scheme}")
    value = re.sub(r"/+", "/", value)
    segments = [segment for segment in value.split("/") if segment]
    if any(segment in {".", "..", "~"} for segment in segments):
        raise ValueError("Path traversal segments are not safe")
    return value.rstrip("/") or "/"


def network_scheme(value):
    return urlsplit((value or "").strip()).scheme.lower()


def is_supported_kodi_network_url(value):
    return network_scheme(value) in SUPPORTED_KODI_NETWORK_SCHEMES


def is_sftp_network_url(value):
    return network_scheme(value) in SFTP_NETWORK_SCHEMES

def redact_url(value):
    if not value:
        return value
    try:
        parts = urlsplit(value)
        if "@" in parts.netloc:
            host = parts.netloc.split("@", 1)[1]
            return urlunsplit((parts.scheme, "***@" + host, parts.path, parts.query, parts.fragment))
    except Exception:
        pass
    return value


def is_path_under(path, parent):
    p = normalise_path(path)
    root = normalise_path(parent)
    return p == root or p.startswith(root.rstrip("/") + "/")


def join_path(base, relative):
    if is_supported_kodi_network_url(base):
        return base.rstrip("/") + "/" + relative.lstrip("/")
    return posixpath.join(base, relative)


def parse_mappings(raw):
    """Parse strict `remote=>kodi` entries separated by semicolons or new lines."""
    mappings = []
    seen = set()
    for entry in re.split(r"[;\n]+", raw or ""):
        entry = entry.strip()
        if not entry:
            continue
        if "=>" not in entry:
            raise ValueError(f"Invalid path mapping entry: {entry}")
        left, right = (part.strip() for part in entry.split("=>", 1))
        if not left or not right:
            raise ValueError(f"Invalid path mapping entry: {entry}")
        pair = (normalise_path(left), normalise_path(right))
        if pair in seen:
            raise ValueError(f"Duplicate path mapping entry: {entry}")
        for existing_left, existing_right in mappings:
            if is_path_under(pair[0], existing_left) or is_path_under(existing_left, pair[0]):
                raise ValueError("Overlapping remote path mappings are ambiguous")
            if is_path_under(pair[1], existing_right) or is_path_under(existing_right, pair[1]):
                raise ValueError("Overlapping Kodi path mappings are ambiguous")
        seen.add(pair)
        mappings.append(pair)
    mappings.sort(key=lambda pair: len(pair[0]), reverse=True)
    return mappings


class PathMapper:
    def __init__(self, mappings):
        self.mappings = list(mappings or [])

    def remote_to_kodi(self, remote_path):
        remote = normalise_path(remote_path)
        for source, target in self.mappings:
            if is_path_under(remote, source):
                suffix = remote[len(source):].lstrip("/")
                return join_path(target, suffix) if suffix else target
        return ""

    def kodi_to_remote(self, kodi_path):
        kodi = normalise_path(kodi_path)
        reverse = sorted(((target, source) for source, target in self.mappings), key=lambda p: len(p[0]), reverse=True)
        for source, target in reverse:
            if is_path_under(kodi, source):
                suffix = kodi[len(source):].lstrip("/")
                return join_path(target, suffix) if suffix else target
        return ""
