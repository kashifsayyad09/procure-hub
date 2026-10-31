"""Request-ID and request logging middleware, and liveness/readiness routes, identical in every service."""
import logging
import time
import uuid
from collections.abc import Callable, Collection

import jwt
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import text
from sqlalchemy.engine import Engine

from .logging import request_id_var
from .service_auth import verify_service_token

log = logging.getLogger("http")


def install_request_context(app: FastAPI, *, no_store_prefix: str | None = None) -> None:
    @app.middleware("http")
    async def request_context(request: Request, call_next):
        rid = (request.headers.get("x-request-id") or str(uuid.uuid4()))[:64]
        token = request_id_var.set(rid)
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            log.exception("unhandled_error", extra={"path": request.url.path, "method": request.method})
            response = JSONResponse({"detail": "Something went wrong. Try again."}, status_code=500)
        response.headers["X-Request-ID"] = rid
        if no_store_prefix and request.url.path.startswith(no_store_prefix):
            response.headers["Cache-Control"] = "no-store"
        log.info("request", extra={
            "method": request.method, "path": request.url.path, "status": response.status_code,
            "duration_ms": round((time.perf_counter() - start) * 1000, 1),
        })
        request_id_var.reset(token)
        return response


def install_health_routes(app: FastAPI, engine: Engine) -> None:
    @app.get("/health/live", tags=["health"])
    def live():
        return {"status": "ok"}

    @app.get("/health/ready", tags=["health"])
    def ready():
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except Exception:
            log.exception("readiness_failed")
            return JSONResponse({"status": "unavailable"}, status_code=503)
        return {"status": "ok"}


_service_bearer = HTTPBearer(auto_error=False)


def service_caller(get_secret: Callable[[Request], str | None], allowed: Collection[str]) -> Callable[..., str]:
    """FastAPI dependency for /internal routes: only a valid token signed by an allowed service is accepted.
    These routes must never be exposed through the public ingress."""

    def dep(request: Request, creds: HTTPAuthorizationCredentials | None = Depends(_service_bearer)) -> str:
        secret = get_secret(request)
        if not secret:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Internal API is not configured.")
        if creds is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Service credentials required.")
        try:
            return verify_service_token(creds.credentials, secret, allowed)
        except jwt.PyJWTError:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid service credentials.") from None

    return dep
