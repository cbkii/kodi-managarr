# SPDX-License-Identifier: GPL-3.0-or-later
import json
import re
import socket
import ssl
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener, HTTPSHandler

from .errors import ApiError

MAX_RESPONSE_BYTES = 8 * 1024 * 1024
MAX_ERROR_BYTES = 16 * 1024


class _SameOriginRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        old = urlsplit(req.full_url)
        new = urlsplit(urljoin(req.full_url, newurl))
        old_port = old.port or (443 if old.scheme == "https" else 80)
        new_port = new.port or (443 if new.scheme == "https" else 80)
        if (old.scheme.lower(), (old.hostname or "").lower(), old_port) != (
            new.scheme.lower(), (new.hostname or "").lower(), new_port
        ):
            raise ApiError("API redirected to a different origin; refusing to forward credentials")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class JsonHttpClient:
    def __init__(self, base_url, api_key, api_version="v3", timeout=15, verify_tls=True, logger=None):
        self.base_url = self._validate_base_url(base_url)
        self.api_key = api_key or ""
        version = self._validate_api_version(api_version)
        self.api_root = f"{self.base_url}/api/{version}"
        self.timeout = timeout
        self.verify_tls = verify_tls
        self.logger = logger

    def request(self, method, path, params=None, payload=None):
        path = "/" + path.lstrip("/")
        url = self.api_root + path
        if params:
            clean = []
            for key, value in params.items():
                if value is None:
                    continue
                if isinstance(value, (list, tuple, set)):
                    clean.extend((key, item) for item in value)
                else:
                    clean.append((key, str(value).lower() if isinstance(value, bool) else value))
            if clean:
                url += "?" + urlencode(clean, doseq=True)

        body = None
        headers = {
            "Accept": "application/json",
            "X-Api-Key": self.api_key,
            "User-Agent": "Kodi-Managarr/0.2",
        }
        if payload is not None:
            body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if self.logger:
            self.logger.debug("HTTP %s %s", method.upper(), self._redact_url(url))

        request = Request(url, data=body, headers=headers, method=method.upper())
        context = None
        if url.lower().startswith("https://") and not self.verify_tls:
            context = ssl._create_unverified_context()  # nosec - explicit user setting
        opener = build_opener(_SameOriginRedirectHandler(), HTTPSHandler(context=context))
        try:
            with opener.open(request, timeout=self.timeout) as response:
                raw = self._read_bounded(response, MAX_RESPONSE_BYTES)
                if not raw:
                    return None
                content_type = response.headers.get("Content-Type", "")
                if "json" not in content_type.lower():
                    raise ApiError("API response was not JSON")
                try:
                    return json.loads(raw.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise ApiError("API response contained invalid JSON") from exc
        except HTTPError as exc:
            raw_bytes = self._read_bounded(exc, MAX_ERROR_BYTES, truncate=True)
            raw = raw_bytes.decode("utf-8", "replace")
            message = f"API request failed with HTTP {exc.code}"
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    safe = parsed.get("message") or parsed.get("error")
                    if isinstance(safe, str) and safe.strip():
                        message = f"{message}: {safe.strip()[:300]}"
            except json.JSONDecodeError:
                pass
            raise ApiError(message, status=exc.code) from exc
        except ApiError:
            raise
        except ssl.SSLError as exc:
            raise ApiError(f"TLS validation failed for {self._redact_url(self.base_url)}") from exc
        except (socket.timeout, TimeoutError) as exc:
            raise ApiError(f"Connection to {self._redact_url(self.base_url)} timed out") from exc
        except URLError as exc:
            reason = type(exc.reason).__name__ if not isinstance(exc.reason, str) else exc.reason[:120]
            raise ApiError(f"Could not connect to {self._redact_url(self.base_url)}: {reason}") from exc

    @staticmethod
    def _read_bounded(response, limit, truncate=False):
        raw = response.read(limit + 1)
        if len(raw) > limit:
            if truncate:
                return raw[:limit]
            raise ApiError("API response exceeded the safe size limit")
        return raw

    @staticmethod
    def _validate_base_url(base_url):
        value = (base_url or "").strip().rstrip("/")
        try:
            parts = urlsplit(value)
            hostname = parts.hostname
            _ = parts.port
        except ValueError as exc:
            raise ApiError("API base URL must be a valid absolute http(s) URL with a host") from exc
        if parts.scheme not in {"http", "https"} or not parts.netloc or not hostname:
            raise ApiError("API base URL must be an absolute http(s) URL with a host")
        if parts.username or parts.password:
            raise ApiError("API base URL must not contain embedded credentials")
        if parts.query or parts.fragment:
            raise ApiError("API base URL must not contain a query string or fragment")
        return value

    @staticmethod
    def _validate_api_version(api_version):
        value = (api_version or "").strip().strip("/")
        if not re.fullmatch(r"v[0-9]+", value):
            raise ApiError("API version must use syntax like v3")
        return value

    @staticmethod
    def _redact_url(value):
        try:
            parts = urlsplit(value or "")
            netloc = parts.netloc.rsplit("@", 1)[-1]
            return parts._replace(netloc=netloc, query="", fragment="").geturl()
        except ValueError:
            return "<redacted-url>"
