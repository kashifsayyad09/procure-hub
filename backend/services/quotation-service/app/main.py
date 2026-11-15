from fastapi import FastAPI
from procurehub_common.dburl import resolve_database_url
from procurehub_common.fastapi_support import install_health_routes, install_request_context
from procurehub_common.logging import configure_logging
from procurehub_common.service_client import ServiceClient
from sqlalchemy.engine import Engine

from .common import Clients
from .config import Settings, get_settings
from .database import make_engine, make_session_factory
from .routers import internal, quotations, rfqs


def create_app(settings: Settings | None = None, engine: Engine | None = None, clients: Clients | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level, "quotation-service")
    engine = engine or make_engine(resolve_database_url(settings.database_url))

    if clients is None:
        secret = settings.internal_jwt_secret.get_secret_value() if settings.internal_jwt_secret else None
        clients = Clients(
            vendors=ServiceClient(settings.vendor_service_url, secret, "quotation-service") if settings.vendor_service_url and secret else None,
            requests=ServiceClient(settings.purchase_request_service_url, secret, "quotation-service") if settings.purchase_request_service_url and secret else None)

    app = FastAPI(
        title="ProcureHub Quotation Service",
        version="0.1.0",
        docs_url="/docs" if settings.docs_enabled else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.docs_enabled else None,
    )
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = make_session_factory(engine)
    app.state.clients = clients

    install_request_context(app)
    install_health_routes(app, engine)
    app.include_router(rfqs.router)
    app.include_router(quotations.router)
    app.include_router(internal.router)
    return app
