from fastapi import FastAPI
from procurehub_common.dburl import resolve_database_url
from procurehub_common.fastapi_support import install_health_routes, install_request_context
from procurehub_common.logging import configure_logging
from sqlalchemy.engine import Engine

from .config import Settings, get_settings
from .database import make_engine, make_session_factory
from .routers import internal, vendors


def create_app(settings: Settings | None = None, engine: Engine | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level, "vendor-service")
    engine = engine or make_engine(resolve_database_url(settings.database_url))

    app = FastAPI(
        title="ProcureHub Vendor Service",
        version="0.1.0",
        docs_url="/docs" if settings.docs_enabled else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.docs_enabled else None,
    )
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = make_session_factory(engine)

    install_request_context(app)
    install_health_routes(app, engine)
    app.include_router(vendors.router)
    app.include_router(internal.router)
    return app
