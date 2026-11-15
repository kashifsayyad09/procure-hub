"""Read-only internal API used by the RFQ service (and later purchase orders)."""
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from procurehub_common.contracts.purchase_request import PurchaseRequestPage, PurchaseRequestRef
from procurehub_common.service_auth import create_service_token

from app.config import Settings
from app.main import create_app
from tests.conftest import SECRET, headers, payload

INTERNAL = "i" * 40
URL = "/api/v1/purchase-requests"


def svc(name="quotation-service", secret=INTERNAL):
    return {"Authorization": f"Bearer {create_service_token(secret, name)}"}


@pytest.fixture
def c(engine):
    return TestClient(create_app(Settings(database_url="sqlite://", jwt_secret=SECRET, internal_jwt_secret=INTERNAL, log_level="CRITICAL"), engine))


@pytest.fixture
def make(c):
    def _make(approve=True, **over):
        r = c.post(URL, headers=headers(), json=payload(**over)).json()
        c.post(f"{URL}/{r['id']}/submit", headers=headers())
        if approve:
            notice = {"decision": "approved", "actor_id": "mgr-1", "actor_name": "Mia Manager", "note": "ok", "decided_at": datetime.now(UTC).isoformat()}
            assert c.post(f"/internal/v1/purchase-requests/{r['id']}/decision", json=notice, headers=svc("approval-service")).status_code == 200
        return r
    return _make


def test_a_request_is_returned_with_its_items_and_exact_totals(c, make):
    r = make()
    resp = c.get(f"/internal/v1/purchase-requests/{r['id']}", headers=svc())
    assert resp.status_code == 200
    ref = PurchaseRequestRef.model_validate(resp.json())
    assert ref.status == "approved" and ref.number == r["number"] and ref.decided_by_name == "Mia Manager" and ref.department == "Design"
    assert [(i.line_no, i.quantity, i.line_total) for i in ref.items] == [(1, Decimal("4.000"), Decimal("96000.00")), (2, Decimal("4.000"), Decimal("3002.00"))]
    assert ref.total_amount == Decimal("99002.00")
    assert "requester_id" not in resp.text and "requester_email" not in resp.text


def test_only_approved_requests_are_listed_and_search_treats_wildcards_literally(c, make):
    a = make(title="Standing desks")
    make(title="Draft only", approve=False)
    make(title="50% discount chairs")
    page = PurchaseRequestPage.model_validate(c.get("/internal/v1/purchase-requests/approved", headers=svc()).json())
    assert page.total == 2 and {i.title for i in page.items} == {"Standing desks", "50% discount chairs"}
    assert [i.title for i in PurchaseRequestPage.model_validate(c.get("/internal/v1/purchase-requests/approved?q=desks", headers=svc()).json()).items] == ["Standing desks"]
    assert c.get(f"/internal/v1/purchase-requests/approved?q={a['number']}", headers=svc()).json()["total"] == 1
    assert c.get("/internal/v1/purchase-requests/approved?q=%25", headers=svc()).json()["total"] == 1  # a literal percent sign
    p2 = c.get("/internal/v1/purchase-requests/approved?page_size=1&page=2", headers=svc()).json()
    assert p2["total"] == 2 and len(p2["items"]) == 1
    assert c.get("/internal/v1/purchase-requests/approved?page_size=101", headers=svc()).status_code == 422


def test_unknown_request_is_404(c):
    assert c.get("/internal/v1/purchase-requests/nope", headers=svc()).status_code == 404


def test_only_listed_services_with_the_right_secret_may_read(c, make):
    r = make()
    for h in ({}, headers("admin", "adm-1"), headers("procurement", "p-1"), svc("approval-service"), svc("random-service"), svc(secret="z" * 40)):
        assert c.get(f"/internal/v1/purchase-requests/{r['id']}", headers=h).status_code == 401, h
        assert c.get("/internal/v1/purchase-requests/approved", headers=h).status_code == 401, h
    assert c.get(f"/internal/v1/purchase-requests/{r['id']}", headers=svc("purchase-order-service")).status_code == 200


def test_disabled_without_a_secret_and_hidden_from_the_docs(client, create):
    r = create()
    assert client.get(f"/internal/v1/purchase-requests/{r['id']}", headers=svc()).status_code == 503
    assert not [p for p in client.get("/openapi.json").json()["paths"] if p.startswith("/internal")]


def test_the_public_api_still_shows_procurement_only_approved_requests(c, make):
    make()
    make(approve=False)
    assert c.get(URL, headers=headers("procurement", "p-1", "Pat")).json()["total"] == 1
