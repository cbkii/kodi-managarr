import json
import re
import socket
import ssl
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from .errors import ApiError


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
        """Send one bounded JSON API request without retrying mutations."""
        path = "/" + path.lstrip("/")
        url = self.api_root + path
        if params:
            clean = []
            for key, value in params.items():
                if value is None:
                    continue
                if isinstance(value, (list, tuple)):
                    clean.extend((key, item) for item in value)
                else:
                    clean.append((key, str(value).lower() if isinstance(value, bool) else value))
            if clean:
                url += "?" + urlencode(clean, doseq=True)

        body = None
        headers = {"Accept": "application/json", "X-Api-Key": self.api_key}
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"

        if self.logger:
            self.logger.debug("HTTP %s %s", method, self._redact_url(url))

        request = Request(url, data=body, headers=headers, method=method.upper())
        context = None
        if url.lower().startswith("https://") and not self.verify_tls:
            context = ssl._create_unverified_context()  # nosec - explicit user setting

        try:
            with urlopen(request, timeout=self.timeout, context=context) as response:
                raw = response.read()
                if not raw:
                    return None
                content_type = response.headers.get("Content-Type", "")
                if "json" not in content_type.lower():
                    raise ApiError("API response was not JSON")
                try:
                    return json.loads(raw.decode("utf-8"))
                except json.JSONDecodeError as exc:
                    raise ApiError("API response contained invalid JSON") from exc
        except HTTPError as exc:
            raw = exc.read().decode("utf-8", "replace")
            message = f"API request failed with HTTP {exc.code}"
            try:
                parsed = json.loads(raw)
                message = parsed.get("message") or parsed.get("error") or message
            except json.JSONDecodeError:
                if raw.strip():
                    message = f"{message}: {raw[:300]}"
            raise ApiError(message, status=exc.code, body=raw) from exc
        except ssl.SSLError as exc:
            raise ApiError(f"TLS validation failed for {self._redact_url(self.base_url)}") from exc
        except (socket.timeout, TimeoutError) as exc:
            raise ApiError(f"Connection to {self._redact_url(self.base_url)} timed out") from exc
        except URLError as exc:
            raise ApiError(f"Could not connect to {self._redact_url(self.base_url)}: {exc.reason}") from exc

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
