from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from app.config import DEFAULT_THRESHOLDS, Settings
from app.models import Approval, ApprovalEvent
from app.rules import levels_for
from tests.conftest import INTERNAL, SECRET, headers, registration, svc

T = DEFAULT_THRESHOLDS


@pytest.mark.parametrize("total,currency,levels", [
    ("0.01", "INR", 1), ("99999.99", "INR", 1), ("100000", "INR", 2), ("999999.99", "INR", 2), ("1000000", "INR", 3), ("25000000", "INR", 3),
    ("1499.99", "USD", 1), ("1500", "USD", 2), ("15000", "USD", 3), ("1199", "GBP", 1), ("12000", "GBP", 3), ("1", "JPY", 3),
])
def test_number_of_approval_levels_depends_on_amount_and_currency(total, currency, levels):
    assert levels_for(Decimal(total), currency, T) == levels


def test_thresholds_must_make_sense():
    for bad in ({"INR": [100]}, {"INR": [5, 5]}, {"INR": [10, 5]}, {"INR": [0, 5]}):
        with pytest.raises(ValidationError):
            Settings(jwt_secret=SECRET, internal_jwt_secret=INTERNAL, approval_thresholds=bad)
    assert Settings(jwt_secret=SECRET, internal_jwt_secret=INTERNAL, approval_thresholds={"INR": [10, 20]}).approval_thresholds["INR"][1] == 20


def test_secrets_are_required_and_must_be_long():
    with pytest.raises(ValidationError):
        Settings(jwt_secret=SECRET)
    with pytest.raises(ValidationError):
        Settings(jwt_secret=SECRET, internal_jwt_secret="short")


def test_internal_endpoints_only_accept_the_purchase_request_service(client):
    body = registration()
    assert client.post("/internal/v1/approvals", json=body).status_code == 401
    assert client.post("/internal/v1/approvals", json=body, headers=headers("admin", "adm")).status_code == 401  # even an admin's user token
    assert client.post("/internal/v1/approvals", json=body, headers=svc("auth-service")).status_code == 401
    assert client.post("/internal/v1/approvals", json=body, headers=svc(secret="z" * 40)).status_code == 401
    assert client.post(f"/internal/v1/approvals/{body['request_id']}/cancel", json={"actor_name": "A"}).status_code == 401
    assert "/internal/v1/approvals" not in client.get("/openapi.json").json()["paths"]


@pytest.mark.parametrize("total,currency,levels", [("50000.00", "INR", 1), ("150000.00", "INR", 2), ("2000000.00", "INR", 3), ("2000.00", "USD", 2)])
def test_registering_creates_the_right_route(client, db, total, currency, levels):
    r = client.post("/internal/v1/approvals", json=registration(total_amount=total, currency=currency), headers=svc())
    assert r.status_code == 200 and r.json()["total_levels"] == levels
    ap = db.scalar(select(Approval))
    assert [s.status for s in ap.steps] == ["pending"] + ["waiting"] * (levels - 1) and ap.current_level == 1 and ap.status == "pending"
    assert ap.steps[0].activated_at is not None and all(s.activated_at is None for s in ap.steps[1:])
    assert [h.action for h in ap.history] == ["requested"] and ap.decision_sync == "not_needed"


def test_registering_twice_returns_the_same_workflow(client, db):
    body = registration()
    first = client.post("/internal/v1/approvals", json=body, headers=svc()).json()
    second = client.post("/internal/v1/approvals", json=body, headers=svc()).json()
    assert first == second
    assert len(db.scalars(select(Approval)).all()) == 1 and len(db.scalars(select(ApprovalEvent)).all()) == 1


def test_registration_is_validated_against_the_contract(client):
    for bad in ({"currency": "JPY"}, {"priority": "asap"}, {"total_amount": "abc"}, {"request_id": ""}, {"title": "x" * 200}):
        assert client.post("/internal/v1/approvals", json=registration(**bad), headers=svc()).status_code == 422
    assert client.post("/internal/v1/approvals", json={"title": "x"}, headers=svc()).status_code == 422


def test_the_snapshot_keeps_what_managers_need_to_decide(client, register):
    aid = register(justification="Because", items=[{"line_no": 1, "description": "Desk", "quantity": "2.5", "unit": "each", "unit_price": "19.99", "line_total": "49.98"}])
    d = client.get(f"/api/v1/approvals/{aid}", headers=headers()).json()
    assert d["justification"] == "Because" and d["requester_name"] == "Alice Employee" and d["items"][0]["line_total"] == "49.98" and d["total_levels"] == 1
