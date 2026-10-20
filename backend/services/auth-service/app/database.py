from collections.abc import Iterator

from fastapi import Request
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker


def make_engine(url: str) -> Engine:
    # pool_pre_ping drops dead connections (RDS failover, idle timeouts); recycle stays under MySQL wait_timeout
    return create_engine(url, pool_pre_ping=True, pool_recycle=1800, future=True)


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db(request: Request) -> Iterator[Session]:
    db = request.app.state.session_factory()
    try:
        yield db
    finally:
        db.close()
