"""
Minimal stdlib JSON HTTP client — no venv or ``pip install`` required, so this
tool runs on any plain ``python3``, including directly on the deploy server.

Mirrors ``backend/scripts/send_correlated_alerts.py``'s ``ApiClient``, but
returns ``(status, body)`` instead of raising, since the generator needs the
raw status to decide what's retryable (429/502/503/504).

Not shared as one module on purpose: this directory must work standalone on a
bare machine with no ``backend/`` checkout present.
"""

from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


class RequestFailed(Exception):
    """Network-level failure — no HTTP response at all (connection refused,
    DNS failure, timeout, TLS error, a dropped VPN tunnel, ...)."""


class ApiClient:
    def __init__(self, base_url: str, *, timeout: float = 30.0, insecure: bool = False) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.headers: dict[str, str] = {}
        self._ssl_context = None
        if insecure:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            self._ssl_context = ctx

    def request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        form: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> tuple[int, Any]:
        url = self.base_url + path
        if params:
            url += "?" + urllib.parse.urlencode(params)

        data: bytes | None = None
        request_headers = dict(self.headers)
        if headers:
            request_headers.update(headers)
        if form is not None:
            data = urllib.parse.urlencode(form).encode()
            request_headers["Content-Type"] = "application/x-www-form-urlencoded"
        elif json_body is not None:
            data = json.dumps(json_body).encode()
            request_headers["Content-Type"] = "application/json"

        req = urllib.request.Request(url, data=data, headers=request_headers, method=method)
        try:
            with urllib.request.urlopen(
                req, timeout=timeout or self.timeout, context=self._ssl_context
            ) as response:
                status = response.status
                body = response.read().decode()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read().decode(errors="replace")
        except OSError as exc:  # covers urllib.error.URLError, TimeoutError, ConnectionError
            raise RequestFailed(str(exc)) from exc

        return status, (json.loads(body) if body else None)

    def get(self, path: str, *, params: dict[str, Any] | None = None) -> tuple[int, Any]:
        return self.request("GET", path, params=params)

    def post(
        self,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        form: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, Any]:
        return self.request("POST", path, json_body=json_body, form=form, headers=headers)
