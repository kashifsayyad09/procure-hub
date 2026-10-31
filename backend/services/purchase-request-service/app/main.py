import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from procurehub_common.dburl import resolve_database_url
from procurehub_common.fastapi_support import install_health_routes, install_request_context
from procurehub_common.logging import configure_logging
from procurehub_common.service_client import ServiceClient
from sqlalchemy.engine import Engine

from . import approvals
from .config import Settings, get_settings
from .database import make_engine, make_session_factory
from .routers import internal, requests

log = logging.getLogger("jobs")


def _reconcile_loop(app: FastAPI, stop: threading.Event) -> None:
    interval = app.state.settings.reconcile_interval_seconds
    while True:
        try:
            with app.state.session_factory() as db:
                done = approvals.reconcile_once(db, app.state.approvals)
            if done:
                log.info("reconciled", extra={"registered": done})
        except Exception:  # keep the loop alive whatever happens
            log.exception("reconcile_failed")
        if stop.wait(interval):
            return


def create_app(settings: Settings | None = None, engine: Engine | None = None, approvals_client: ServiceClient | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level, "purchase-request-service")
    engine = engine or make_engine(resolve_database_url(settings.database_url))
    if approvals_client is None and settings.approval_service_url and settings.internal_jwt_secret:
        approvals_client = ServiceClient(settings.approval_service_url, settings.internal_jwt_secret.get_secret_value(), "purchase-request-service")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        stop, thread = threading.Event(), None
        if settings.background_jobs and app.state.approvals is not None:
            thread = threading.Thread(target=_reconcile_loop, args=(app, stop), daemon=True, name="approval-reconcile")
            thread.start()
        yield
        stop.set()
        if thread:
            thread.join(timeout=5)

    app = FastAPI(
        title="ProcureHub Purchase Request Service",
        version="0.2.0",
        docs_url="/docs" if settings.docs_enabled else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.docs_enabled else None,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = make_session_factory(engine)
    app.state.approvals = approvals_client

    install_request_context(app)
    install_health_routes(app, engine)
    app.include_router(requests.router)
    app.include_router(internal.router)
    return app
