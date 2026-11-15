import jwt
import pytest

from tests.conftest import PROC, QUO, RFQ, VA, headers, make_token

STAFF_ENDPOINTS = [
    ("get", f"{RFQ}", None), ("post", f"{RFQ}", {"purchase_request_id": "pr-1", "deadline": "2099-01-01T00:00:00Z"}), ("get", f"{RFQ}/summary", None),
    ("get", f"{RFQ}/eligible-requests", None), ("get", f"{RFQ}/ID", None), ("put", f"{RFQ}/ID", {"version": 1, "title": "abc", "deadline": "2099-01-01T00:00:00Z"}),
    ("post", f"{RFQ}/ID/publish", None), ("post", f"{RFQ}/ID/close", None), ("post", f"{RFQ}/ID/cancel", {"reason": "abc"}),
    ("post", f"{RFQ}/ID/extend", {"version": 1, "deadline": "2099-01-01T00:00:00Z"}), ("post", f"{RFQ}/ID/invitations", {"vendor_ids": ["v-a"]}),
    ("post", f"{RFQ}/ID/invitations/X/withdraw", None), ("get", f"{RFQ}/ID/quotations", None), ("get", f"{RFQ}/ID/comparison", None),
    ("put", f"{RFQ}/ID/evaluations/Q", {"compliance_score": 5, "compliance_note": "x"}),
    ("post", f"{RFQ}/ID/selection", {"quotation_id": "Q", "justification": "A long enough reason."}), ("get", f"{RFQ}/ID/selection", None),
    ("get", f"{RFQ}/ID/selection/history", None), ("post", f"{RFQ}/ID/selection/revoke", {"reason": "A reason"}),
]
VENDOR_ENDPOINTS = [
    ("get", f"{RFQ}/invited", None), ("get", f"{RFQ}/invited/ID", None), ("post", f"{RFQ}/invited/ID/decline", None), ("get", f"{QUO}/mine", None),
    ("post", QUO, {"rfq_id": "ID", "currency": "INR", "items": []}), ("put", f"{QUO}/ID", {"version": 1, "currency": "INR", "items": []}),
    ("post", f"{QUO}/ID/submit", None), ("post", f"{QUO}/ID/withdraw", None),
]
SHARED = [("get", f"{QUO}/ID", None)]


def call(client, method, url, body, h=None):
    kw = {"headers": h} if h else {}
    if body is not None:
        kw["json"] = body
    return getattr(client, method)(url, **kw)


@pytest.mark.parametrize("method,url,body", STAFF_ENDPOINTS + VENDOR_ENDPOINTS + SHARED)
def test_every_endpoint_rejects_anonymous_callers(client, method, url, body):
    assert call(client, method, url, body).status_code == 401


@pytest.mark.parametrize("role,sub", [("employee", "emp-1"), ("manager", "mgr-1"), ("finance", "fin-1"), ("admin", "adm-1"), ("superuser", "x")])
def test_roles_with_no_rfq_permissions_are_refused_everywhere(client, role, sub):
    h = headers(role, sub)
    for method, url, body in STAFF_ENDPOINTS + VENDOR_ENDPOINTS + SHARED:
        assert call(client, method, url, body, h).status_code == 403, (role, method, url)


@pytest.mark.parametrize("method,url,body", STAFF_ENDPOINTS)
def test_vendors_cannot_use_procurement_endpoints(client, method, url, body):
    assert call(client, method, url, body, VA).status_code == 403


@pytest.mark.parametrize("method,url,body", VENDOR_ENDPOINTS)
def test_procurement_cannot_use_vendor_endpoints(client, method, url, body):
    assert call(client, method, url, body, PROC).status_code == 403


@pytest.mark.parametrize("bad", [
    {"Authorization": "Bearer garbage"}, {"Authorization": "Basic abc"}, headers(secret="y" * 40), headers(aud="other"), headers(iss="other"), headers(ttl=-5), headers(typ="refresh"),
    {"Authorization": f"Bearer {make_token(alg='HS512')}"},
])
def test_invalid_tokens_are_rejected(client, bad):
    assert client.get(RFQ, headers=bad).status_code == 401
    assert client.get(f"{RFQ}/invited", headers=bad).status_code == 401


def test_an_unsigned_token_is_rejected(client):
    forged = jwt.encode({"sub": "x", "role": "procurement", "typ": "access", "iss": "procurehub-auth", "aud": "procurehub", "iat": 1, "exp": 9999999999}, None, algorithm="none")
    assert client.get(RFQ, headers={"Authorization": f"Bearer {forged}"}).status_code == 401


def test_the_role_comes_from_the_signed_token_not_from_headers_or_query(client):
    assert client.get(f"{RFQ}?role=procurement", headers={**VA, "X-Role": "procurement"}).status_code == 403
    assert client.get(f"{RFQ}/invited?role=vendor", headers={**PROC, "X-Role": "vendor"}).status_code == 403


def test_the_approved_request_check_cannot_be_bypassed_by_naming_another_requests_data(client, clock, world):
    from tests.conftest import rfq_body
    world.add_request("pr-9", "PR-2026-000009", status="rejected")
    r = client.post(RFQ, headers=PROC, json=rfq_body(clock, purchase_request_id="pr-9", **{"status": "approved", "budget_amount": "1"}))
    assert r.status_code == 422  # the request's real status is read from the purchase request service, not taken from the body


def test_mass_assignment_into_an_rfq_is_ignored(client, make_rfq, clock):
    from tests.conftest import rfq_body
    r = client.post(RFQ, headers=PROC, json=rfq_body(clock, status="awarded", number="RFQ-1", budget_amount="1.00", version=9, created_by_name="Mallory", currency="USD"))
    assert r.status_code == 201
    out = r.json()
    assert out["status"] == "draft" and out["number"] != "RFQ-1" and out["budget_amount"] == "99002.00" and out["version"] == 1 and out["created_by_name"] == "Pat Procurement" and out["currency"] == "INR"


def test_unknown_rfqs_are_404(client):
    assert client.get(f"{RFQ}/invited/nope", headers=VA).status_code == 404
    assert client.get(f"{RFQ}/nope", headers=PROC).status_code == 404
