from datetime import datetime

import pytest
from sqlalchemy import select

from app.models import Approval, ApprovalEvent, ApprovalHistory
from tests.conftest import headers, make_token

URL = "/api/v1/approvals"
M1, M2, M3 = headers(sub="mgr-1", name="Mia Manager"), headers(sub="mgr-2", name="Max Manager"), headers(sub="mgr-3", name="Mona Manager")


def test_a_single_level_approval_updates_the_request_service(client, register, purchase):
    aid = register("50000.00")
    r = client.post(f"{URL}/{aid}/approve", json={"comment": "Looks right"}, headers=M1)
    assert r.status_code == 200
    d = r.json()
    assert d["status"] == "approved" and d["decided_at"] and d["decision_sync"] == "synced" and d["can_decide"] is False
    [(path, body)] = purchase.calls
    assert path.endswith("/decision") and body["decision"] == "approved" and body["actor_id"] == "mgr-1" and body["actor_name"] == "Mia Manager" and body["note"] == "Looks right"
    assert [h["action"] for h in d["history"]] == ["requested", "approved"] and d["history"][1]["actor_name"] == "Mia Manager"


def test_a_two_level_request_needs_two_different_managers(client, register, purchase):
    aid = register("150000.00")
    first = client.post(f"{URL}/{aid}/approve", json={}, headers=M1).json()
    assert first["status"] == "pending" and first["current_level"] == 2 and [s["status"] for s in first["steps"]] == ["approved", "pending"]
    assert purchase.calls == []  # the requester hears nothing until the final decision
    again = client.post(f"{URL}/{aid}/approve", json={}, headers=M1)
    assert again.status_code == 403 and "different manager" in again.json()["detail"]
    final = client.post(f"{URL}/{aid}/approve", json={"comment": "Second sign-off"}, headers=M2).json()
    assert final["status"] == "approved" and final["decision_sync"] == "synced"
    assert purchase.calls[0][1]["actor_id"] == "mgr-2" and purchase.calls[0][1]["note"] == "Second sign-off"


def test_three_levels_for_a_very_large_request(client, register):
    aid = register("2000000.00")
    for who in (M1, M2, M3):
        d = client.post(f"{URL}/{aid}/approve", json={}, headers=who).json()
    assert d["status"] == "approved" and [s["status"] for s in d["steps"]] == ["approved"] * 3


def test_rejection_needs_a_reason_and_ends_the_workflow(client, register, purchase):
    aid = register("2000000.00")
    client.post(f"{URL}/{aid}/approve", json={}, headers=M1)
    for bad in ({}, {"reason": ""}, {"reason": "no"}, {"reason": "  "}):
        assert client.post(f"{URL}/{aid}/reject", json=bad, headers=M2).status_code == 422
    d = client.post(f"{URL}/{aid}/reject", json={"reason": "Over budget this quarter"}, headers=M2).json()
    assert d["status"] == "rejected" and [s["status"] for s in d["steps"]] == ["approved", "rejected", "skipped"] and d["decision_sync"] == "synced"
    assert purchase.calls[0][1]["decision"] == "rejected" and purchase.calls[0][1]["note"] == "Over budget this quarter" and purchase.calls[0][1]["actor_id"] == "mgr-2"
    assert client.post(f"{URL}/{aid}/approve", json={}, headers=M3).status_code == 409


def test_a_decided_request_cannot_be_decided_again(client, register):
    aid = register()
    client.post(f"{URL}/{aid}/approve", json={}, headers=M1)
    for call in (lambda: client.post(f"{URL}/{aid}/approve", json={}, headers=M2), lambda: client.post(f"{URL}/{aid}/reject", json={"reason": "changed my mind"}, headers=M2),
                 lambda: client.post(f"{URL}/{aid}/delegate", json={"user_id": "mgr-3"}, headers=M2)):
        r = call()
        assert r.status_code == 409 and "already approved" in r.json()["detail"]


def test_a_manager_cannot_decide_their_own_request(client, register):
    aid = register(requester_id="mgr-1", requester_name="Mia Manager")
    r = client.post(f"{URL}/{aid}/approve", json={}, headers=M1)
    assert r.status_code == 403 and "own request" in r.json()["detail"]
    assert client.post(f"{URL}/{aid}/reject", json={"reason": "my own"}, headers=M1).status_code == 403
    d = client.get(f"{URL}/{aid}", headers=M1).json()
    assert d["can_decide"] is False and "own request" in d["blocked_reason"]
    assert client.post(f"{URL}/{aid}/approve", json={}, headers=M2).status_code == 200


def test_unknown_approval_is_404(client):
    assert client.get(f"{URL}/nope", headers=M1).status_code == 404
    assert client.post(f"{URL}/nope/approve", json={}, headers=M1).status_code == 404
    assert client.post(f"{URL}/nope/reject", json={"reason": "abc"}, headers=M1).status_code == 404


ENDPOINTS = [("get", URL, None), ("get", f"{URL}/summary", None), ("get", f"{URL}/delegates", None), ("get", f"{URL}/x", None),
             ("post", f"{URL}/x/approve", {}), ("post", f"{URL}/x/reject", {"reason": "abc"}), ("post", f"{URL}/x/delegate", {"user_id": "u"})]


def test_every_endpoint_rejects_anonymous_callers(client):
    for method, url, body in ENDPOINTS:
        r = getattr(client, method)(url, **({"json": body} if body is not None else {}))
        assert r.status_code == 401, (method, url)


@pytest.mark.parametrize("role", ["employee", "procurement", "vendor", "finance", "admin", "superuser"])
def test_only_managers_can_use_approvals(client, register, role):
    aid = register()
    h = headers(role, f"{role}-1")
    for method, url, body in ENDPOINTS:
        r = getattr(client, method)(url.replace("/x", f"/{aid}"), headers=h, **({"json": body} if body is not None else {}))
        assert r.status_code == 403, (role, method, url)
    assert client.get(f"{URL}/{aid}", headers=M1).json()["status"] == "pending"


@pytest.mark.parametrize("bad", [{"Authorization": "Bearer garbage"}, headers(secret="y" * 40), headers(aud="other"), headers(ttl=-5), headers(typ="refresh"),
                                 {"Authorization": f"Bearer {make_token(aud='procurehub-internal', typ='service')}"}])
def test_invalid_tokens_are_rejected(client, bad):
    assert client.get(URL, headers=bad).status_code == 401


def test_a_service_token_cannot_be_used_on_the_public_api(client):
    from tests.conftest import svc
    assert client.get(URL, headers=svc()).status_code == 401


def test_history_keeps_its_order_when_timestamps_are_identical(client, register, db):
    aid = register("150000.00")
    client.post(f"{URL}/{aid}/approve", json={}, headers=M1)
    client.post(f"{URL}/{aid}/delegate", json={"user_id": "mgr-3"}, headers=M2)
    client.post(f"{URL}/{aid}/approve", json={}, headers=M3)
    same = datetime(2026, 1, 1, 12, 0, 0)  # MySQL DATETIME has whole-second precision
    for h in db.scalars(select(ApprovalHistory)).all():
        h.created_at = same
    db.commit()
    assert [h["action"] for h in client.get(f"{URL}/{aid}", headers=M1).json()["history"]] == ["requested", "approved", "delegated", "approved"]


def test_every_change_writes_an_outbox_event_in_the_same_transaction(client, register, db):
    a = register("150000.00")
    client.post(f"{URL}/{a}/approve", json={}, headers=M1)
    client.post(f"{URL}/{a}/delegate", json={"user_id": "mgr-3"}, headers=M2)
    client.post(f"{URL}/{a}/approve", json={}, headers=M3)
    b = register("50000.00")
    client.post(f"{URL}/{b}/reject", json={"reason": "not now"}, headers=M1)
    events = db.scalars(select(ApprovalEvent).order_by(ApprovalEvent.created_at, ApprovalEvent.id)).all()
    assert sorted(e.type for e in events) == sorted(["approval.requested", "approval.step_approved", "approval.delegated", "approval.approved", "approval.requested", "approval.rejected"])
    assert all(e.published_at is None for e in events)
    assert "password" not in " ".join(e.payload for e in events).lower() and "Bearer" not in " ".join(e.payload for e in events)
    assert db.scalar(select(Approval).where(Approval.id == a)).status == "approved"
