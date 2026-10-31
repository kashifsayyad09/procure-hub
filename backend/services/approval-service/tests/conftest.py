import json
import os
import uuid
from datetime import UTC, datetime, timedelta

import httpx
import jwt
import pytest
from fastapi.testclient import TestClient
from procurehub_common.service_auth import create_service_token, verify_service_token
from procurehub_common.service_client import ServiceClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.main import create_app
from app.models import Base

SECRET, INTERNAL = "x" * 40, "i" * 40


def make_token(role="manager", sub="mgr-1", name="Mia Manager", email="mia@example.com", *, secret=SECRET, aud="procurehub", iss="procurehub-auth", ttl=900, typ="access"):
    now = datetime.now(UTC)
    return jwt.encode({"iss": iss, "aud": aud, "sub": sub, "role": role, "name": name, "email": email, "typ": typ, "iat": now, "exp": now + timedelta(seconds=ttl)}, secret, algorithm="HS256")


def headers(role="manager", sub="mgr-1", name="Mia Manager", **kw):
    return {"Authorization": f"Bearer {make_token(role, sub, name, **kw)}"}


def svc(name="purchase-request-service", secret=INTERNAL):
    return {"Authorization": f"Bearer {create_service_token(secret, name)}"}


class FakePurchaseService:
    """Stands in for the Purchase Request service."""

    def __init__(self):
        self.calls: list[tuple[str, dict]] = []
        self.mode = "up"  # up, down, error, conflict

    def __call__(self, req: httpx.Request) -> httpx.Response:
        if self.mode == "down":
            raise httpx.ConnectError("refused")
        if self.mode == "error":
            return httpx.Response(503, json={"detail": "busy"})
        assert verify_service_token(req.headers["authorization"].split()[1], INTERNAL, {"approval-service"}) == "approval-service"
        self.calls.append((req.url.path, json.loads(req.content)))
        if self.mode == "conflict":
            return httpx.Response(409, json={"detail": "Request is cancelled; only a submitted request can be decided."})
        return httpx.Response(200, json={"status": "ok"})


MANAGERS = [{"id": "mgr-1", "full_name": "Mia Manager", "email": "mia@example.com"}, {"id": "mgr-2", "full_name": "Max Manager", "email": "max@example.com"},
            {"id": "mgr-3", "full_name": "Mona Manager", "email": "mona@example.com"}, {"id": "emp-a", "full_name": "Alice Employee", "email": "alice@example.com"}]


class FakeAuthService:
    def __init__(self):
        self.mode = "up"

    def __call__(self, req: httpx.Request) -> httpx.Response:
        if self.mode == "down":
            raise httpx.ConnectError("refused")
        assert req.url.path == "/internal/v1/users" and req.url.params["role"] == "manager"
        return httpx.Response(200, json=MANAGERS)


@pytest.fixture
def settings():
    return Settings(database_url="sqlite://", jwt_secret=SECRET, internal_jwt_secret=INTERNAL, background_jobs=False, log_level="CRITICAL")


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
def purchase():
    return FakePurchaseService()


@pytest.fixture
def auth():
    return FakeAuthService()


@pytest.fixture
def app(settings, engine, purchase, auth):
    pc = ServiceClient("http://purchase", INTERNAL, "approval-service", transport=httpx.MockTransport(purchase), attempts=1)
    ac = ServiceClient("http://auth", INTERNAL, "approval-service", transport=httpx.MockTransport(auth), attempts=1)
    return create_app(settings, engine, purchase_client=pc, auth_client=ac)


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def db(app):
    with app.state.session_factory() as s:
        yield s


def registration(**over):
    base = {"request_id": str(uuid.uuid4()), "request_number": "PR-2026-000001", "title": "Standing desks", "justification": "Back pain", "department": "Facilities",
            "priority": "normal", "currency": "INR", "total_amount": "50000.00", "requester_id": "emp-a", "requester_name": "Alice Employee",
            "requester_email": "alice@example.com", "submitted_at": "2026-03-01T10:00:00",
            "items": [{"line_no": 1, "description": "Desk", "quantity": "2", "unit": "each", "unit_price": "25000.00", "line_total": "50000.00"}]}
    return base | over


@pytest.fixture
def register(client):
    """Registers a request through the internal API and returns the approval id."""
    def _register(total="50000.00", **over):
        r = client.post("/internal/v1/approvals", json=registration(total_amount=total, **over), headers=svc())
        assert r.status_code == 200, r.text
        return r.json()["id"]
    return _register
