from datetime import timedelta

import pytest
from sqlalchemy import select

from app import service
from app.models import Approval, ApprovalEvent, utcnow
from tests.conftest import headers, registration, svc

URL = "/api/v1/approvals"
M1, M2, M3 = headers(sub="mgr-1", name="Mia Manager"), headers(sub="mgr-2", name="Max Manager"), headers(sub="mgr-3", name="Mona Manager")


# ---- delegation ----------------------------------------------------------------------------------------
def test_a_delegated_approval_can_only_be_decided_by_the_delegate(client, register):
    aid = register()
    d = client.post(f"{URL}/{aid}/delegate", json={"user_id": "mgr-2", "note": "I am away"}, headers=M1)
    assert d.status_code == 200
    out = d.json()
    assert out["waiting_for"] == "Max Manager" and out["steps"][0]["assigned_to_id"] == "mgr-2"
    assert out["history"][-1]["action"] == "delegated" and "Max Manager" in out["history"][-1]["note"] and "I am away" in out["history"][-1]["note"]
    for who, expected in ((M1, 403), (M3, 403)):
        r = client.post(f"{URL}/{aid}/approve", json={}, headers=who)
        assert r.status_code == expected and "delegated to Max Manager" in r.json()["detail"]
    assert client.get(f"{URL}/{aid}", headers=M2).json()["can_decide"] is True
    assert client.get(f"{URL}/{aid}", headers=M1).json()["can_decide"] is False
    assert client.post(f"{URL}/{aid}/approve", json={}, headers=M2).json()["status"] == "approved"


def test_the_delegate_can_pass_it_on(client, register):
    aid = register()
    client.post(f"{URL}/{aid}/delegate", json={"user_id": "mgr-2"}, headers=M1)
    assert client.post(f"{URL}/{aid}/delegate", json={"user_id": "mgr-3"}, headers=M2).status_code == 200
    assert client.post(f"{URL}/{aid}/approve", json={}, headers=M2).status_code == 403
    assert client.post(f"{URL}/{aid}/approve", json={}, headers=M3).status_code == 200


@pytest.mark.parametrize("target,message", [("mgr-1", "different manager"), ("emp-a", "person who made the request"), ("ghost", "active manager"), ("", None)])
def test_delegation_targets_are_checked(client, register, target, message):
    aid = register()
    r = client.post(f"{URL}/{aid}/delegate", json={"user_id": target}, headers=M1)
    assert r.status_code == 422
    if message:
        assert message in str(r.json()["detail"])


def test_cannot_delegate_to_someone_who_already_approved_an_earlier_level(client, register):
    aid = register("150000.00")
    client.post(f"{URL}/{aid}/approve", json={}, headers=M1)
    r = client.post(f"{URL}/{aid}/delegate", json={"user_id": "mgr-1"}, headers=M2)
    assert r.status_code == 422 and "already approved" in r.json()["detail"]


def test_delegates_list_excludes_the_caller_and_needs_the_auth_service(client, auth, app):
    ids = [m["id"] for m in client.get(f"{URL}/delegates", headers=M1).json()]
    assert "mgr-1" not in ids and {"mgr-2", "mgr-3"} <= set(ids)
    auth.mode = "down"
    assert client.get(f"{URL}/delegates", headers=M1).status_code == 503
    aid = client.post("/internal/v1/approvals", json=registration(), headers=svc()).json()["id"]
    assert client.post(f"{URL}/{aid}/delegate", json={"user_id": "mgr-2"}, headers=M1).status_code == 503
    app.state.auth_client = None
    assert client.get(f"{URL}/delegates", headers=M1).status_code == 503


# ---- keeping the Purchase Request service in step ------------------------------------------------------
@pytest.mark.parametrize("mode", ["down", "error"])
def test_a_decision_is_kept_and_retried_when_the_request_service_is_unavailable(client, register, purchase, app, mode):
    aid = register()
    purchase.mode = mode
    r = client.post(f"{URL}/{aid}/approve", json={"comment": "ok"}, headers=M1)
    assert r.status_code == 200 and r.json()["status"] == "approved"  # the manager is never blocked by another service's outage
    assert r.json()["decision_sync"] == "pending" and r.json()["last_sync_error"]
    with app.state.session_factory() as db:
        assert service.reconcile_once(db, app.state.purchase_client, 48) == (0, 0)  # still down
        assert db.get(Approval, aid).sync_attempts == 2
    purchase.mode = "up"
    with app.state.session_factory() as db:
        assert service.reconcile_once(db, app.state.purchase_client, 48) == (1, 0)
        assert service.reconcile_once(db, app.state.purchase_client, 48) == (0, 0)  # nothing left
    assert len(purchase.calls) == 1 and purchase.calls[0][1]["decision"] == "approved" and purchase.calls[0][1]["note"] == "ok"
    d = client.get(f"{URL}/{aid}", headers=M1).json()
    assert d["decision_sync"] == "synced" and d["last_sync_error"] is None


def test_a_refused_decision_is_recorded_as_a_conflict_and_not_retried(client, register, purchase, app, db):
    aid = register()
    purchase.mode = "conflict"
    d = client.post(f"{URL}/{aid}/approve", json={}, headers=M1).json()
    assert d["status"] == "approved" and d["decision_sync"] == "conflict" and "cancelled" in d["last_sync_error"]
    assert d["history"][-1]["action"] == "sync_conflict"
    assert "approval.sync_conflict" in [e.type for e in db.scalars(select(ApprovalEvent)).all()]
    n = len(purchase.calls)
    purchase.mode = "up"
    with app.state.session_factory() as s:
        assert service.reconcile_once(s, app.state.purchase_client, 48) == (0, 0)
    assert len(purchase.calls) == n


def test_without_a_request_service_configured_decisions_wait(client, register, app):
    aid = register()
    app.state.purchase_client = None
    d = client.post(f"{URL}/{aid}/approve", json={}, headers=M1).json()
    assert d["status"] == "approved" and d["decision_sync"] == "pending"


def test_cancelling_from_the_request_service_closes_the_workflow(client, register, db):
    aid = register("150000.00")
    rid = db.get(Approval, aid).request_id
    r = client.post(f"/internal/v1/approvals/{rid}/cancel", json={"actor_name": "Alice Employee", "reason": "Budget frozen"}, headers=svc())
    assert r.status_code == 200 and r.json() == {"status": "cancelled"}
    d = client.get(f"{URL}/{aid}", headers=M1).json()
    assert d["status"] == "cancelled" and {s["status"] for s in d["steps"]} == {"skipped"} and d["history"][-1]["note"] == "Budget frozen" and d["waiting_for"] is None
    assert client.post(f"{URL}/{aid}/approve", json={}, headers=M1).status_code == 409  # nothing left to approve
    assert client.post(f"/internal/v1/approvals/{rid}/cancel", json={"actor_name": "A"}, headers=svc()).json() == {"status": "cancelled"}  # idempotent
    assert client.post("/internal/v1/approvals/unknown/cancel", json={"actor_name": "A"}, headers=svc()).json() == {"status": "unknown"}


def test_cancelling_after_a_decision_changes_nothing(client, register, db):
    aid = register()
    client.post(f"{URL}/{aid}/approve", json={}, headers=M1)
    assert client.post(f"/internal/v1/approvals/{db.get(Approval, aid).request_id}/cancel", json={"actor_name": "A"}, headers=svc()).json() == {"status": "approved"}


# ---- escalation ----------------------------------------------------------------------------------------
def test_a_request_that_waits_too_long_is_flagged_overdue_once(client, register, app, db):
    aid = register()
    step = db.get(Approval, aid).steps[0]
    step.activated_at = utcnow() - timedelta(hours=49)
    db.commit()
    assert client.get(f"{URL}/{aid}", headers=M1).json()["overdue"] is False
    with app.state.session_factory() as s:
        assert service.reconcile_once(s, app.state.purchase_client, 48) == (0, 1)
        assert service.reconcile_once(s, app.state.purchase_client, 48) == (0, 0)
    d = client.get(f"{URL}/{aid}", headers=M1).json()
    assert d["overdue"] is True and d["steps"][0]["escalated_at"] and d["history"][-1]["action"] == "escalated" and d["history"][-1]["actor_name"] == "System"
    assert "approval.escalated" in [e.type for e in db.scalars(select(ApprovalEvent)).all()]
    assert client.post(f"{URL}/{aid}/approve", json={}, headers=M2).status_code == 200  # escalation only flags; anyone eligible can still decide


def test_recent_and_decided_requests_are_never_escalated(client, register, app, db):
    fresh, decided = register(), register()
    client.post(f"{URL}/{decided}/approve", json={}, headers=M1)
    for aid in (fresh, decided):
        for s in db.get(Approval, aid).steps:
            s.activated_at = utcnow() - timedelta(hours=1 if aid == fresh else 100)
    db.commit()
    with app.state.session_factory() as s:
        assert service.reconcile_once(s, app.state.purchase_client, 48) == (0, 0)


def test_the_next_level_starts_its_own_clock(client, register, app, db):
    aid = register("150000.00")
    db.get(Approval, aid).steps[0].activated_at = utcnow() - timedelta(hours=60)
    db.commit()
    client.post(f"{URL}/{aid}/approve", json={}, headers=M1)
    db.expire_all()
    with app.state.session_factory() as s:
        assert service.reconcile_once(s, app.state.purchase_client, 48) == (0, 0)  # level 2 only just began
