import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import jwt
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from procurehub_common.contracts.approval import ApprovalRegistration
from procurehub_common.service_auth import create_service_token, verify_service_token
from procurehub_common.service_client import ServiceClient
from sqlalchemy import create_engine, text

from app import approvals
from app.config import Settings
from app.main import create_app
from app.models import PurchaseRequest
from tests.conftest import SECRET, headers, payload

URL = "/api/v1/purchase-requests"
INTERNAL = "i" * 40
ROOT = Path(__file__).resolve().parent.parent


class FakeApproval:
    """Stands in for the Approval service: records calls, can be switched off or made to reject."""

    def __init__(self):
        self.calls: list[tuple[str, str, dict, str]] = []
        self.mode = "up"

    def __call__(self, req: httpx.Request) -> httpx.Response:
        if self.mode == "down":
            raise httpx.ConnectError("refused")
        if self.mode == "error":
            return httpx.Response(503, json={"detail": "busy"})
        caller = verify_service_token(req.headers["authorization"].split()[1], INTERNAL, {"purchase-request-service"})
        self.calls.append((req.method, req.url.path, json.loads(req.content or b"{}"), caller))
        if self.mode == "reject":
            return httpx.Response(422, json={"detail": "bad contract"})
        return httpx.Response(200, json={"ok": True})


@pytest.fixture
def fake():
    return FakeApproval()


@pytest.fixture
def wired(engine, fake):
    s = Settings(database_url="sqlite://", jwt_secret=SECRET, internal_jwt_secret=INTERNAL, approval_service_url="http://approval", background_jobs=False, log_level="CRITICAL")
    client = ServiceClient("http://approval", INTERNAL, "purchase-request-service", transport=httpx.MockTransport(fake), attempts=1)
    app = create_app(s, engine, approvals_client=client)
    return app, TestClient(app)


def _submit(c, **over):
    r = c.post(URL, headers=headers(), json=payload(**over)).json()
    return r, c.post(f"{URL}/{r['id']}/submit", headers=headers())


def _row(app, rid):
    with app.state.session_factory() as db:
        return db.get(PurchaseRequest, rid)


def test_submit_registers_the_request_with_the_approval_service(wired, fake):
    app, c = wired
    r, s = _submit(c)
    assert s.status_code == 200 and s.json()["status"] == "submitted"
    [(method, path, body, caller)] = fake.calls
    assert (method, path, caller) == ("POST", "/internal/v1/approvals", "purchase-request-service")
    reg = ApprovalRegistration(**body)  # the receiver validates against the same contract
    assert reg.request_id == r["id"] and reg.request_number == r["number"] and str(reg.total_amount) == "99002.00" and reg.currency == "INR"
    assert reg.requester_id == "emp-a" and reg.requester_name == "Alice Employee" and reg.requester_email == "alice@example.com"
    assert [i.line_total for i in reg.items] == [96000, 3002] and reg.justification and reg.department == "Design"
    assert _row(app, r["id"]).approval_registered is True


def test_submit_still_succeeds_when_the_approval_service_is_down_and_a_retry_registers_it(wired, fake):
    app, c = wired
    fake.mode = "down"
    r, s = _submit(c)
    assert s.status_code == 200 and s.json()["status"] == "submitted"  # the employee is not blocked by another service's outage
    assert _row(app, r["id"]).approval_registered is False
    with app.state.session_factory() as db:
        assert approvals.reconcile_once(db, app.state.approvals) == 0  # still down
    fake.mode = "up"
    with app.state.session_factory() as db:
        assert approvals.reconcile_once(db, app.state.approvals) == 1
        assert approvals.reconcile_once(db, app.state.approvals) == 0  # nothing left to do
    assert _row(app, r["id"]).approval_registered is True
    assert fake.calls[-1][2]["request_id"] == r["id"]


@pytest.mark.parametrize("mode", ["error", "reject"])
def test_failed_registration_never_breaks_submit(wired, fake, mode):
    app, c = wired
    fake.mode = mode
    r, s = _submit(c)
    assert s.status_code == 200 and _row(app, r["id"]).approval_registered is False


def test_the_retry_only_picks_up_submitted_unregistered_requests(wired, fake):
    app, c = wired
    draft = c.post(URL, headers=headers(), json=payload()).json()
    cancelled, _ = _submit(c)
    c.post(f"{URL}/{cancelled['id']}/cancel", headers=headers(), json={"reason": "not needed"})
    with app.state.session_factory() as db:
        db.get(PurchaseRequest, cancelled["id"]).approval_registered = False
        db.commit()
    fake.calls.clear()
    with app.state.session_factory() as db:
        assert approvals.reconcile_once(db, app.state.approvals) == 0
    assert fake.calls == [] and _row(app, draft["id"]).approval_registered is False


def test_cancel_tells_the_approval_service_and_survives_its_outage(wired, fake):
    app, c = wired
    r, _ = _submit(c)
    fake.mode = "down"
    ok = c.post(f"{URL}/{r['id']}/cancel", headers=headers(), json={"reason": "Budget frozen"})
    assert ok.status_code == 200 and ok.json()["status"] == "cancelled"
    fake.mode = "up"
    r2, _ = _submit(c)
    fake.calls.clear()
    c.post(f"{URL}/{r2['id']}/cancel", headers=headers(), json={"reason": "Budget frozen"})
    [(method, path, body, _)] = fake.calls
    assert (method, path) == ("POST", f"/internal/v1/approvals/{r2['id']}/cancel") and body["reason"] == "Budget frozen" and body["actor_name"] == "Alice Employee"


def test_no_approval_service_configured_means_no_calls_and_no_errors(client, create):
    r = create()
    assert client.post(f"{URL}/{r['id']}/submit", headers=headers()).status_code == 200


# ---- internal decision endpoint ------------------------------------------------------------------------
def svc(name="approval-service", secret=INTERNAL):
    return {"Authorization": f"Bearer {create_service_token(secret, name)}"}


def decision(decision="approved", note="Looks right", actor="mgr-1"):
    return {"decision": decision, "actor_id": actor, "actor_name": "Mia Manager", "note": note, "decided_at": datetime.now(UTC).isoformat()}


def _internal(c, rid):
    return f"/internal/v1/purchase-requests/{rid}/decision"


def test_decision_endpoint_rejects_everything_but_the_approval_service(wired):
    app, c = wired
    r, _ = _submit(c)
    url = _internal(c, r["id"])
    assert c.post(url, json=decision()).status_code == 401
    assert c.post(url, json=decision(), headers=headers("admin", "adm-1")).status_code == 401  # a user token, even an admin's
    assert c.post(url, json=decision(), headers=svc("purchase-request-service")).status_code == 401
    assert c.post(url, json=decision(), headers=svc(secret="z" * 40)).status_code == 401
    assert c.get(URL + f"/{r['id']}", headers=headers()).json()["status"] == "submitted"


def test_decision_endpoint_is_disabled_without_an_internal_secret_and_hidden(client, create):
    r = create()
    assert client.post(_internal(client, r["id"]), json=decision(), headers=svc()).status_code == 503
    assert "/internal/v1/purchase-requests/{request_id}/decision" not in client.get("/openapi.json").json()["paths"]


def test_approval_decision_updates_the_request_and_its_history(wired):
    app, c = wired
    r, _ = _submit(c)
    resp = c.post(_internal(c, r["id"]), json=decision(), headers=svc())
    assert resp.status_code == 200 and resp.json() == {"status": "approved"}
    out = c.get(f"{URL}/{r['id']}", headers=headers()).json()
    assert out["status"] == "approved" and out["decided_by_name"] == "Mia Manager" and out["decision_note"] == "Looks right" and out["decided_at"] and out["version"] == 3
    last = out["history"][-1]
    assert (last["from_status"], last["to_status"], last["actor_name"], last["note"]) == ("submitted", "approved", "Mia Manager", "Looks right")
    assert c.put(f"{URL}/{r['id']}", headers=headers(), json=payload() | {"version": 3}).status_code == 409  # decided requests stay locked


def test_rejection_keeps_the_reason_visible_to_the_employee(wired):
    app, c = wired
    r, _ = _submit(c)
    assert c.post(_internal(c, r["id"]), json=decision("rejected", "Over budget this quarter"), headers=svc()).status_code == 200
    out = c.get(f"{URL}/{r['id']}", headers=headers()).json()
    assert out["status"] == "rejected" and out["decision_note"] == "Over budget this quarter"


def test_repeating_the_same_decision_is_harmless_but_a_conflicting_one_is_refused(wired):
    app, c = wired
    r, _ = _submit(c)
    assert c.post(_internal(c, r["id"]), json=decision(), headers=svc()).status_code == 200
    assert c.post(_internal(c, r["id"]), json=decision(), headers=svc()).status_code == 200  # retry after a lost response
    out = c.get(f"{URL}/{r['id']}", headers=headers()).json()
    assert out["version"] == 3 and len([h for h in out["history"] if h["to_status"] == "approved"]) == 1
    assert c.post(_internal(c, r["id"]), json=decision("rejected", "changed my mind"), headers=svc()).status_code == 409
    assert c.get(f"{URL}/{r['id']}", headers=headers()).json()["status"] == "approved"


@pytest.mark.parametrize("prepare", ["draft", "cancelled"])
def test_only_a_submitted_request_can_be_decided(wired, prepare):
    app, c = wired
    r = c.post(URL, headers=headers(), json=payload()).json()
    if prepare == "cancelled":
        c.post(f"{URL}/{r['id']}/submit", headers=headers())
        c.post(f"{URL}/{r['id']}/cancel", headers=headers(), json={"reason": "no longer needed"})
    resp = c.post(_internal(c, r["id"]), json=decision(), headers=svc())
    assert resp.status_code == 409 and prepare in resp.json()["detail"]


def test_decision_endpoint_validates_the_contract(wired):
    app, c = wired
    r, _ = _submit(c)
    url = _internal(c, r["id"])
    assert c.post(url, json=decision() | {"decision": "maybe"}, headers=svc()).status_code == 422
    assert c.post(url, json={"decision": "approved"}, headers=svc()).status_code == 422
    assert c.post(_internal(c, "nope"), json=decision(), headers=svc()).status_code == 404


def test_settings_require_an_internal_secret_when_the_approval_url_is_set():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        Settings(database_url="sqlite://", jwt_secret=SECRET, approval_service_url="http://approval")
    with pytest.raises(ValidationError):
        Settings(database_url="sqlite://", jwt_secret=SECRET, internal_jwt_secret="short")


def test_service_tokens_cannot_be_used_as_user_tokens(client):
    token = create_service_token(SECRET, "approval-service")
    assert client.get(URL, headers={"Authorization": f"Bearer {token}"}).status_code == 401
    assert jwt.decode(token, SECRET, algorithms=["HS256"], audience="procurehub-internal")["typ"] == "service"


# ---- upgrading a Phase 3 database --------------------------------------------------------------------
def test_upgrade_from_phase_3_keeps_data_and_queues_submitted_requests_for_registration(tmp_path, monkeypatch, fake):
    url = f"sqlite:///{tmp_path / 'phase3.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    command.upgrade(cfg, "0001")  # the Phase 3 schema
    eng = create_engine(url)
    with eng.begin() as conn:
        conn.execute(text("INSERT INTO purchase_requests (id, number, requester_id, requester_name, requester_email, department, title, justification, priority, currency, status, "
                          "total_amount, version, created_at, updated_at, submitted_at) VALUES ('old-1','PR-2026-000007','emp-a','Alice','a@example.com','IT','Old request','Why','normal','INR',"
                          "'submitted',500.00,2,'2026-01-01 10:00:00','2026-01-01 10:00:00','2026-01-01 10:00:00')"))
    command.upgrade(cfg, "head")
    s = Settings(database_url=url, jwt_secret=SECRET, internal_jwt_secret=INTERNAL, approval_service_url="http://approval", background_jobs=False, log_level="CRITICAL")
    client = ServiceClient("http://approval", INTERNAL, "purchase-request-service", transport=httpx.MockTransport(fake), attempts=1)
    app = create_app(s, eng, approvals_client=client)
    with app.state.session_factory() as db:
        row = db.get(PurchaseRequest, "old-1")
        assert row.approval_registered is False and row.decision_note is None and row.title == "Old request"
        assert approvals.reconcile_once(db, client) == 1
    assert fake.calls[0][2]["request_number"] == "PR-2026-000007"
    command.downgrade(cfg, "0001")
