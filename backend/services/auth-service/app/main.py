import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.engine import Engine

from .config import Settings, get_settings
from .database import make_engine, make_session_factory
from .dburl import resolve_database_url
from .logging_setup import configure_logging, request_id_var
from .routers import auth, users

log = logging.getLogger("http")


def create_app(settings: Settings | None = None, engine: Engine | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)
    engine = engine or make_engine(resolve_database_url(settings.database_url))

    app = FastAPI(
        title="ProcureHub Authentication Service",
        version="0.1.0",
        docs_url="/docs" if settings.docs_enabled else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.docs_enabled else None,
    )
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = make_session_factory(engine)

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        rid = request.headers.get("x-request-id") or str(uuid.uuid4())
        token = request_id_var.set(rid[:64])
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            log.exception("unhandled_error", extra={"path": request.url.path, "method": request.method})
            response = JSONResponse({"detail": "Something went wrong. Try again."}, status_code=500)
        response.headers["X-Request-ID"] = rid[:64]
        if request.url.path.startswith("/api/v1/auth"):
            response.headers["Cache-Control"] = "no-store"
        log.info("request", extra={
            "method": request.method, "path": request.url.path, "status": response.status_code,
            "duration_ms": round((time.perf_counter() - start) * 1000, 1),
        })
        request_id_var.reset(token)
        return response

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

    app.include_router(auth.router)
    app.include_router(users.router)
    return app
