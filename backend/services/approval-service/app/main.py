import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from procurehub_common.dburl import resolve_database_url
from procurehub_common.fastapi_support import install_health_routes, install_request_context
from procurehub_common.logging import configure_logging
from procurehub_common.service_client import ServiceClient
from sqlalchemy.engine import Engine

from . import service
from .config import Settings, get_settings
from .database import make_engine, make_session_factory
from .routers import approvals, internal

log = logging.getLogger("jobs")


def _loop(app: FastAPI, stop: threading.Event) -> None:
    s = app.state.settings
    while True:
        try:
            with app.state.session_factory() as db:
                delivered, escalated = service.reconcile_once(db, app.state.purchase_client, s.escalation_hours)
            if delivered or escalated:
                log.info("reconciled", extra={"decisions_delivered": delivered, "escalated": escalated})
        except Exception:  # keep the loop alive whatever happens
            log.exception("reconcile_failed")
        if stop.wait(s.reconcile_interval_seconds):
            return


def create_app(settings: Settings | None = None, engine: Engine | None = None, purchase_client: ServiceClient | None = None,
               auth_client: ServiceClient | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level, "approval-service")
    engine = engine or make_engine(resolve_database_url(settings.database_url))
    secret = settings.internal_jwt_secret.get_secret_value()
    if purchase_client is None and settings.purchase_request_service_url:
        purchase_client = ServiceClient(settings.purchase_request_service_url, secret, "approval-service")
    if auth_client is None and settings.auth_service_url:
        auth_client = ServiceClient(settings.auth_service_url, secret, "approval-service")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        stop, thread = threading.Event(), None
        if settings.background_jobs:
            thread = threading.Thread(target=_loop, args=(app, stop), daemon=True, name="approval-reconcile")
            thread.start()
        yield
        stop.set()
        if thread:
            thread.join(timeout=5)

    app = FastAPI(
        title="ProcureHub Approval Service",
        version="0.1.0",
        docs_url="/docs" if settings.docs_enabled else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.docs_enabled else None,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = make_session_factory(engine)
    app.state.purchase_client = purchase_client
    app.state.auth_client = auth_client

    install_request_context(app)
    install_health_routes(app, engine)
    app.include_router(approvals.router)
    app.include_router(internal.router)
    return app
