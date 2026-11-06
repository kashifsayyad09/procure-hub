import os
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi.testclient import TestClient
from procurehub_common.service_auth import create_service_token
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.main import create_app
from app.models import Base

SECRET, INTERNAL = "x" * 40, "i" * 40
URL = "/api/v1/vendors"


def make_token(role="vendor", sub="ven-a", name="Vera Vendor", email="vera@acme.example", *, secret=SECRET, aud="procurehub", iss="procurehub-auth",
               ttl=900, typ="access", alg="HS256"):
    now = datetime.now(UTC)
    claims = {"iss": iss, "aud": aud, "sub": sub, "role": role, "name": name, "email": email, "typ": typ, "iat": now, "exp": now + timedelta(seconds=ttl)}
    return jwt.encode(claims, secret, algorithm=alg)


def headers(role="vendor", sub="ven-a", name="Vera Vendor", **kw):
    return {"Authorization": f"Bearer {make_token(role, sub, name, **kw)}"}


def svc(name="quotation-service", secret=INTERNAL):
    return {"Authorization": f"Bearer {create_service_token(secret, name)}"}


VENDOR_A = headers("vendor", "ven-a", "Vera Vendor")
VENDOR_B = headers("vendor", "ven-b", "Victor Vendor")
PROC = headers("procurement", "proc-1", "Pat Procurement")
PROC2 = headers("procurement", "proc-2", "Paul Procurement")
ADMIN = headers("admin", "adm-1", "Ada Admin")


@pytest.fixture
def settings():
    return Settings(database_url="sqlite://", jwt_secret=SECRET, internal_jwt_secret=INTERNAL, log_level="CRITICAL")


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
    base = {
        "legal_name": "Acme Supplies Private Limited", "trade_name": "Acme Supplies", "tax_id": "29ABCDE1234F1Z5", "registration_number": "U12345KA2015PTC080000",
        "website": "https://acme.example", "description": "Office and IT supplies.",
        "address_line1": "12 Industrial Layout", "address_line2": "Peenya", "city": "Bengaluru", "state": "Karnataka", "postal_code": "560058", "country": "IN",
        "payment_terms_days": 30, "currency": "INR", "categories": ["it_hardware", "office_supplies"],
        "contacts": [{"name": "Vera Vendor", "job_title": "Sales lead", "email": "vera@acme.example", "phone": "+91 98765 43210", "is_primary": True}],
    }
    base.update(over)
    return base


@pytest.fixture
def register(client):
    """Registers the vendor owned by the caller (default: vendor user A)."""
    def _register(h=None, **over):
        r = client.post(URL, headers=h or VENDOR_A, json=payload(**over))
        assert r.status_code == 201, r.text
        return r.json()
    return _register


@pytest.fixture
def onboard(client):
    """Registers a vendor as staff, with no owner."""
    def _onboard(h=None, **over):
        r = client.post(f"{URL}/onboard", headers=h or PROC, json=payload(**over))
        assert r.status_code == 201, r.text
        return r.json()
    return _onboard


@pytest.fixture
def pending(client, register):
    """A vendor user's complete profile, submitted and waiting for a reviewer."""
    def _pending(h=None, **over):
        v = register(h, **over)
        r = client.post(f"{URL}/{v['id']}/submit", headers=h or VENDOR_A)
        assert r.status_code == 200, r.text
        return r.json()
    return _pending
