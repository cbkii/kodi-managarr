import json
import ssl
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .errors import ApiError


class JsonHttpClient:
    def __init__(self, base_url, api_key, api_version="v3", timeout=15, verify_tls=True, logger=None):
        self.base_url = (base_url or "").rstrip("/")
        self.api_key = api_key or ""
        self.api_root = f"{self.base_url}/api/{api_version.strip('/')}"
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
            self.logger.debug("HTTP %s %s", method, url)

        request = Request(url, data=body, headers=headers, method=method.upper())
        context = None
        if url.lower().startswith("https://") and not self.verify_tls:
            context = ssl._create_unverified_context()  # nosec - explicit user setting

        try:
            with urlopen(request, timeout=self.timeout, context=context) as response:
                raw = response.read()
                if not raw:
                    return None
                return json.loads(raw.decode("utf-8"))
        except HTTPError as exc:
            raw = exc.read().decode("utf-8", "replace")
            message = f"API request failed with HTTP {exc.code}"
            try:
                parsed = json.loads(raw)
                message = parsed.get("message") or parsed.get("error") or message
            except Exception:
                if raw.strip():
                    message = f"{message}: {raw[:300]}"
            raise ApiError(message, status=exc.code, body=raw) from exc
        except URLError as exc:
            raise ApiError(f"Could not connect to {self.base_url}: {exc.reason}") from exc
        except TimeoutError as exc:
            raise ApiError(f"Connection to {self.base_url} timed out") from exc
