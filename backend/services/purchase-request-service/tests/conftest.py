import os
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.main import create_app
from app.models import Base

SECRET = "x" * 40


def make_token(role="employee", sub="emp-a", name="Alice Employee", email="alice@example.com", *, secret=SECRET, aud="procurehub", iss="procurehub-auth",
               ttl=900, typ="access", alg="HS256"):
    now = datetime.now(UTC)
    claims = {"iss": iss, "aud": aud, "sub": sub, "role": role, "name": name, "email": email, "typ": typ, "iat": now, "exp": now + timedelta(seconds=ttl)}
    return jwt.encode(claims, secret, algorithm=alg)


def headers(role="employee", sub="emp-a", name="Alice Employee", **kw):
    return {"Authorization": f"Bearer {make_token(role, sub, name, **kw)}"}


@pytest.fixture
def settings():
    return Settings(database_url="sqlite://", jwt_secret=SECRET, log_level="CRITICAL")


@pytest.fixture
def engine():
    """In-memory SQLite by default. Set TEST_DATABASE_URL to a scratch MySQL database to run the whole suite on MySQL."""
    url = os.environ.get("TEST_DATABASE_URL")
    if url:
        eng = create_engine(url, pool_pre_ping=True)
        Base.metadata.drop_all(eng)
        Base.metadata.create_all(eng)
        yield eng
        Base.metadata.drop_all(eng)
        eng.dispose()
    else:
        eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(eng)
        yield eng


@pytest.fixture
def app(settings, engine):
    return create_app(settings, engine)


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def db(app):
    with app.state.session_factory() as session:
        yield session


def payload(**over):
    from datetime import date
    base = {
        "title": "Laptops for the design team", "justification": "Current machines cannot run the design tools.", "department": "Design",
        "priority": "normal", "needed_by": str(date.today() + timedelta(days=14)), "currency": "INR",
        "items": [{"description": "14-inch laptop", "quantity": "4", "unit": "each", "unit_price": "24000.00", "notes": "16 GB memory"},
                  {"description": "Laptop sleeve", "quantity": "4", "unit": "each", "unit_price": "750.50"}],
    }
    base.update(over)
    return base


@pytest.fixture
def create(client):
    def _create(h=None, **over):
        r = client.post("/api/v1/purchase-requests", headers=h or headers(), json=payload(**over))
        assert r.status_code == 201, r.text
        return r.json()
    return _create
