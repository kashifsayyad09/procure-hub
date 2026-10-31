"""Small HTTP client for calling another ProcureHub service. Short timeouts, a retry on network errors only, request-ID
propagation, and two clear failure types so callers decide what to retry later."""
import logging
import time
from typing import Any

import httpx

from .logging import request_id_var
from .service_auth import create_service_token

log = logging.getLogger("service_client")


class ServiceUnavailable(Exception):
    """The other service could not be reached, or answered with a server error. Safe to retry later."""


class ServiceRejected(Exception):
    """The other service understood the call and said no (a 4xx). Retrying the same call will not help."""

    def __init__(self, status_code: int, detail: Any):
        super().__init__(f"{status_code}: {detail}")
        self.status_code = status_code
        self.detail = detail


class ServiceClient:
    def __init__(self, base_url: str, secret: str, service_name: str, *, timeout: float = 3.0, attempts: int = 2, transport: httpx.BaseTransport | None = None):
        self.base_url, self.secret, self.service_name = base_url.rstrip("/"), secret, service_name
        self.timeout, self.attempts, self.transport = timeout, attempts, transport

    def request(self, method: str, path: str, json: Any = None, params: dict | None = None) -> Any:
        headers = {"Authorization": f"Bearer {create_service_token(self.secret, self.service_name)}", "X-Request-ID": request_id_var.get()}
        last: Exception | None = None
        for attempt in range(self.attempts):
            try:
                with httpx.Client(base_url=self.base_url, timeout=self.timeout, transport=self.transport) as c:
                    r = c.request(method, path, json=json, params=params, headers=headers)
            except httpx.HTTPError as e:
                last = e
                time.sleep(0.2 * (attempt + 1))
                continue
            if r.status_code >= 500:
                raise ServiceUnavailable(f"{self.base_url}{path} answered {r.status_code}")
            if r.status_code >= 400:
                try:
                    detail = r.json().get("detail")
                except ValueError:
                    detail = r.text[:200]
                raise ServiceRejected(r.status_code, detail)
            return r.json() if r.content else None
        log.warning("service_unreachable", extra={"url": f"{self.base_url}{path}", "error": type(last).__name__})
        raise ServiceUnavailable(f"{self.base_url}{path} is unreachable") from last

    def post(self, path: str, json: Any = None) -> Any:
        return self.request("POST", path, json=json)

    def get(self, path: str, params: dict | None = None) -> Any:
        return self.request("GET", path, params=params)
