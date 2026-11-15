import os
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import httpx
import jwt
import pytest
from fastapi.testclient import TestClient
from procurehub_common.service_auth import create_service_token, verify_service_token
from procurehub_common.service_client import ServiceClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app import evaluation, outputs, service
from app.common import Clients
from app.config import Settings
from app.main import create_app
from app.models import Base
from app.routers import rfqs as rfqs_router

SECRET, INTERNAL = "x" * 40, "i" * 40
RFQ = "/api/v1/rfqs"
QUO = "/api/v1/quotations"


def make_token(role="procurement", sub="proc-1", name="Pat Procurement", *, secret=SECRET, aud="procurehub", iss="procurehub-auth", ttl=900, typ="access", alg="HS256"):
    now = datetime.now(UTC)
    claims = {"iss": iss, "aud": aud, "sub": sub, "role": role, "name": name, "email": f"{sub}@example.com", "typ": typ, "iat": now, "exp": now + timedelta(seconds=ttl)}
    return jwt.encode(claims, secret, algorithm=alg)


def headers(role="procurement", sub="proc-1", name="Pat Procurement", **kw):
    return {"Authorization": f"Bearer {make_token(role, sub, name, **kw)}"}


PROC = headers("procurement", "proc-1", "Pat Procurement")
PROC2 = headers("procurement", "proc-2", "Paul Procurement")
ADMIN = headers("admin", "adm-1", "Ada Admin")
VA = headers("vendor", "u-va", "Vera Vendor")
VB = headers("vendor", "u-vb", "Victor Vendor")
VC = headers("vendor", "u-vc", "Valerie Vendor")
VX = headers("vendor", "u-vx", "Xavier Unverified")
VNONE = headers("vendor", "u-none", "Nora Newcomer")  # a vendor user who has not registered a company
EMP = headers("employee", "emp-1", "Erin Employee")
MGR = headers("manager", "mgr-1", "Mia Manager")
FIN = headers("finance", "fin-1", "Fay Finance")


def svc_header(name="purchase-order-service", secret=INTERNAL):
    return {"Authorization": f"Bearer {create_service_token(secret, name)}"}


class Clock:
    """The time the service sees. Tests move it to cross deadlines without sleeping."""

    def __init__(self):
        self.now = datetime.now(UTC).replace(tzinfo=None, microsecond=0)

    def advance(self, **kw):
        self.now += timedelta(**kw)


class World:
    """Stand-ins for the vendor service and the purchase request service that speak their real internal contracts."""

    def __init__(self):
        self.vendor_down = self.pr_down = False
        self.vendors: dict[str, dict] = {}
        self.owners: dict[str, str] = {}
        self.requests: dict[str, dict] = {}
        self.calls: list[tuple[str, str, str]] = []
        self.add_request("pr-1", "PR-2026-000001")
        for vid, owner, name, status in (("v-a", "u-va", "Acme Supplies", "verified"), ("v-b", "u-vb", "Bravo Traders", "verified"),
                                         ("v-c", "u-vc", "Cedar Co", "verified"), ("v-x", "u-vx", "Xenon Pending Ltd", "pending")):
            self.add_vendor(vid, owner, name, status)

    def add_vendor(self, vid, owner, name, status="verified"):
        self.vendors[vid] = {"contract_version": 1, "id": vid, "number": f"VND-2026-{len(self.vendors) + 1:06d}", "legal_name": name, "trade_name": None, "status": status,
                             "country": "IN", "currency": "INR", "payment_terms_days": 30, "categories": ["it_hardware"], "primary_contact_name": name,
                             "primary_contact_email": f"{vid}@example.com"}
        self.owners[owner] = vid

    def add_request(self, rid, number, status="approved", currency="INR", items=None):
        items = items or [("14-inch laptop", "4.000", "24000.00"), ("Laptop sleeve", "4.000", "750.50")]
        lines = [{"line_no": n, "description": d, "quantity": q, "unit": "each", "unit_price": p, "line_total": str((Decimal(q) * Decimal(p)).quantize(Decimal("0.01")))}
                 for n, (d, q, p) in enumerate(items, start=1)]
        self.requests[rid] = {"contract_version": 1, "id": rid, "number": number, "title": "Laptops for the design team", "justification": "Needed", "department": "Design",
                              "priority": "normal", "currency": currency, "total_amount": str(sum(Decimal(i["line_total"]) for i in lines)),
                              "needed_by": str(date.today() + timedelta(days=30)), "status": status, "requester_name": "Erin Employee",
                              "decided_at": "2026-03-01T10:00:00", "decided_by_name": "Mia Manager", "items": lines}

    def _check(self, req: httpx.Request, who: str):
        token = req.headers["authorization"].split()[1]
        verify_service_token(token, INTERNAL, {"quotation-service"})
        self.calls.append((who, req.method, req.url.path))

    def vendor_handler(self, req: httpx.Request) -> httpx.Response:
        if self.vendor_down:
            raise httpx.ConnectError("down")
        self._check(req, "vendor")
        path = req.url.path
        if path == "/internal/v1/vendors/lookup":
            ids = httpx.Response(200, content=req.content).json()["ids"]
            return httpx.Response(200, json=[self.vendors[i] for i in ids if i in self.vendors])
        if path.startswith("/internal/v1/vendors/by-owner/"):
            vid = self.owners.get(path.rsplit("/", 1)[1])
            return httpx.Response(200, json=self.vendors[vid]) if vid else httpx.Response(404, json={"detail": "No vendor is registered for this user."})
        return httpx.Response(404, json={"detail": "nope"})

    def pr_handler(self, req: httpx.Request) -> httpx.Response:
        if self.pr_down:
            raise httpx.ConnectError("down")
        self._check(req, "pr")
        path = req.url.path
        if path == "/internal/v1/purchase-requests/approved":
            q = req.url.params.get("q", "").lower()
            rows = [r for r in self.requests.values() if r["status"] == "approved" and (q in r["title"].lower() or q in r["number"].lower())]
            page, size = int(req.url.params.get("page", 1)), int(req.url.params.get("page_size", 20))
            return httpx.Response(200, json={"items": rows[(page - 1) * size: page * size], "total": len(rows), "page": page, "page_size": size})
        rid = path.rsplit("/", 1)[1]
        return httpx.Response(200, json=self.requests[rid]) if rid in self.requests else httpx.Response(404, json={"detail": "Purchase request not found."})


@pytest.fixture
def world():
    return World()


@pytest.fixture
def clock(monkeypatch):
    c = Clock()
    for mod in (service, evaluation, outputs, rfqs_router):
        monkeypatch.setattr(mod, "utcnow", lambda: c.now)
    return c


@pytest.fixture
def settings():
    return Settings(database_url="sqlite://", jwt_secret=SECRET, internal_jwt_secret=INTERNAL, log_level="CRITICAL")


@pytest.fixture
def engine():
    """In-memory SQLite by default. Set TEST_DATABASE_URL to a scratch MySQL database to run the whole suite on MySQL."""
    url = os.environ.get("TEST_DATABASE_URL")
    if url:
        eng = create_engine(url, pool_pre_ping=True, pool_size=10)
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
def clients(world):
    return Clients(vendors=ServiceClient("http://vendor", INTERNAL, "quotation-service", transport=httpx.MockTransport(world.vendor_handler), attempts=1),
                   requests=ServiceClient("http://pr", INTERNAL, "quotation-service", transport=httpx.MockTransport(world.pr_handler), attempts=1))


@pytest.fixture
def app(settings, engine, clients, clock):
    return create_app(settings, engine, clients)


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def db(app):
    with app.state.session_factory() as session:
        yield session


def rfq_body(clock, **over):
    base = {"purchase_request_id": "pr-1", "description": "Laptops for the design team.", "requirements": "Warranty of 3 years.",
            "deadline": (clock.now + timedelta(hours=48)).isoformat() + "Z"}
    base.update(over)
    return base


@pytest.fixture
def make_rfq(client, clock):
    def _make(h=None, **over):
        r = client.post(RFQ, headers=h or PROC, json=rfq_body(clock, **over))
        assert r.status_code == 201, r.text
        return r.json()
    return _make


@pytest.fixture
def issued(client, make_rfq):
    """An issued RFQ with vendors A, B and C invited."""
    def _issued(vendors=("v-a", "v-b", "v-c"), **over):
        rfq = make_rfq(**over)
        r = client.post(f"{RFQ}/{rfq['id']}/invitations", headers=PROC, json={"vendor_ids": list(vendors)})
        assert r.status_code == 201, r.text
        r = client.post(f"{RFQ}/{rfq['id']}/publish", headers=PROC)
        assert r.status_code == 200, r.text
        return r.json()
    return _issued


@pytest.fixture
def quote(client):
    """Creates a draft quotation as a vendor, prices the lines in order, and submits it unless told not to."""
    def _quote(h, rfq, prices=("23000.00", "700.00"), *, submit=True, currency="INR", lead=14, days_valid=60, **over):
        valid = (date.today() + timedelta(days=days_valid)).isoformat()
        body = {"rfq_id": rfq["id"], "currency": currency, "lead_time_days": lead, "valid_until": valid, "payment_terms_days": 30, "terms": "Delivery included.",
                "items": [{"rfq_item_id": it["id"], "unit_price": p} for it, p in zip(rfq["items"], prices, strict=False) if p is not None]}
        body.update(over)
        r = client.post(QUO, headers=h, json=body)
        assert r.status_code == 201, r.text
        q = r.json()
        if submit:
            s = client.post(f"{QUO}/{q['id']}/submit", headers=h)
            assert s.status_code == 200, s.text
            q = s.json()
        return q
    return _quote
