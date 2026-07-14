import base64
import hashlib
import os
import posixpath
import re
import unicodedata
from urllib.parse import unquote, urlsplit, urlunsplit


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


def normalise_path(value):
    value = unquote((value or "").strip()).replace("\\", "/")
    if value.startswith("smb://"):
        parts = urlsplit(value)
        path = re.sub(r"/+", "/", parts.path).rstrip("/")
        netloc = parts.netloc.rsplit("@", 1)[-1].lower()
        return urlunsplit((parts.scheme.lower(), netloc, path, "", ""))
    value = re.sub(r"/+", "/", value)
    return value.rstrip("/") or "/"


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
    p = normalise_path(path).casefold()
    root = normalise_path(parent).casefold()
    return p == root or p.startswith(root.rstrip("/") + "/")


def join_path(base, relative):
    if base.startswith("smb://"):
        return base.rstrip("/") + "/" + relative.lstrip("/")
    return posixpath.join(base, relative)


def parse_mappings(raw):
    """Parse `remote=>kodi` entries separated by semicolons or new lines."""
    mappings = []
    for entry in re.split(r"[;\n]+", raw or ""):
        entry = entry.strip()
        if not entry:
            continue
        if "=>" not in entry:
            continue
        left, right = (part.strip() for part in entry.split("=>", 1))
        if left and right:
            mappings.append((normalise_path(left), normalise_path(right)))
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


def sha256_fingerprint(key_bytes):
    digest = hashlib.sha256(key_bytes).digest()
    return "SHA256:" + base64.b64encode(digest).decode("ascii").rstrip("=")
