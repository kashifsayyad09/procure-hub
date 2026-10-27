import pytest

from app.models import PurchaseRequest, Status
from tests.conftest import headers, make_token, payload

URL = "/api/v1/purchase-requests"
DOC = {"file_name": "q.pdf", "content_type": "application/pdf", "size_bytes": 10}

A = headers("employee", "emp-a", "Alice Employee")
B = headers("employee", "emp-b", "Bob Employee")


def _endpoints(rid="some-id"):
    return [("get", URL, None), ("post", URL, payload()), ("get", f"{URL}/summary", None), ("get", f"{URL}/{rid}", None),
            ("put", f"{URL}/{rid}", payload() | {"version": 1}), ("post", f"{URL}/{rid}/submit", None), ("post", f"{URL}/{rid}/cancel", {"reason": "abc"}),
            ("delete", f"{URL}/{rid}", None), ("post", f"{URL}/{rid}/documents", DOC), ("delete", f"{URL}/{rid}/documents/x", None)]


def test_every_endpoint_rejects_anonymous_callers(client):
    for method, url, body in _endpoints():
        r = getattr(client, method)(url, **({"json": body} if body is not None else {}))
        assert r.status_code == 401, (method, url)


@pytest.mark.parametrize("bad", [
    {"Authorization": "Bearer garbage"}, {"Authorization": "Basic abc"}, headers(secret="y" * 40), headers(aud="other"), headers(iss="other"), headers(ttl=-5),
    headers(typ="refresh"), {"Authorization": f"Bearer {make_token(alg='HS512')}"},
])
def test_invalid_tokens_are_rejected(client, bad):
    assert client.get(URL, headers=bad).status_code == 401


def test_unsigned_token_is_rejected(client):
    import jwt
    forged = jwt.encode({"sub": "x", "role": "employee", "typ": "access", "iss": "procurehub-auth", "aud": "procurehub", "iat": 1, "exp": 9999999999}, None, algorithm="none")
    assert client.get(URL, headers={"Authorization": f"Bearer {forged}"}).status_code == 401


@pytest.mark.parametrize("role", ["vendor", "finance", "admin", "manager"])
def test_roles_without_request_permissions_are_forbidden(client, create, role):
    r = create()
    h = headers(role, f"{role}-1")
    assert client.get(URL, headers=h).status_code == 403
    assert client.get(f"{URL}/{r['id']}", headers=h).status_code == 403
    assert client.post(URL, headers=h, json=payload()).status_code == 403
    assert client.get(f"{URL}/summary", headers=h).status_code == 403


def test_unknown_role_in_a_valid_token_gets_nothing(client):
    assert client.get(URL, headers=headers("superuser")).status_code == 403
    assert client.post(URL, headers=headers("superuser"), json=payload()).status_code == 403


def test_employees_cannot_see_each_others_requests(client, create):
    mine = create(A)
    assert client.get(f"{URL}/{mine['id']}", headers=B).status_code == 404  # not 403: existence is not revealed
    assert client.get(URL, headers=B).json()["total"] == 0
    assert client.get(URL, headers=A).json()["total"] == 1
    assert client.get(f"{URL}/summary", headers=B).json()["counts"]["draft"] == 0


def test_employees_cannot_change_each_others_requests(client, create):
    mine = create(A)
    rid = mine["id"]
    assert client.put(f"{URL}/{rid}", headers=B, json=payload(title="Hijacked") | {"version": 1}).status_code == 404
    assert client.post(f"{URL}/{rid}/submit", headers=B).status_code == 404
    assert client.post(f"{URL}/{rid}/documents", headers=B, json=DOC).status_code == 404
    assert client.delete(f"{URL}/{rid}", headers=B).status_code == 404
    client.post(f"{URL}/{rid}/submit", headers=A)
    assert client.post(f"{URL}/{rid}/cancel", headers=B, json={"reason": "not mine"}).status_code == 404
    assert client.get(f"{URL}/{rid}", headers=A).json()["status"] == "submitted"


def test_requester_identity_comes_from_the_token_not_the_body(client):
    r = client.post(URL, headers=A, json=payload() | {"requester_id": "emp-b", "requester_name": "Bob", "status": "approved", "number": "PR-1", "total_amount": "1.00"})
    assert r.status_code == 201
    out = r.json()
    assert out["requester_id"] == "emp-a" and out["requester_name"] == "Alice Employee" and out["status"] == "draft" and out["number"] != "PR-1" and out["total_amount"] != "1.00"


def test_procurement_sees_only_approved_requests_and_cannot_change_them(client, create, db):
    draft, submitted, approved = create(A), create(A), create(A)
    for rid, st in ((submitted["id"], Status.SUBMITTED), (approved["id"], Status.APPROVED)):
        row = db.get(PurchaseRequest, rid)
        row.status = st.value
        db.commit()
    p = headers("procurement", "proc-1", "Pat Procurement")
    page = client.get(URL, headers=p).json()
    assert page["total"] == 1 and page["items"][0]["id"] == approved["id"]
    assert client.get(f"{URL}/{approved['id']}", headers=p).status_code == 200
    assert client.get(f"{URL}/{submitted['id']}", headers=p).status_code == 404
    assert client.get(f"{URL}/{draft['id']}", headers=p).status_code == 404
    rid = approved["id"]
    assert client.post(URL, headers=p, json=payload()).status_code == 403
    assert client.put(f"{URL}/{rid}", headers=p, json=payload() | {"version": 1}).status_code == 403
    assert client.post(f"{URL}/{rid}/submit", headers=p).status_code == 403
    assert client.post(f"{URL}/{rid}/cancel", headers=p, json={"reason": "abc"}).status_code == 403
    assert client.delete(f"{URL}/{rid}", headers=p).status_code == 403
    assert client.post(f"{URL}/{rid}/documents", headers=p, json=DOC).status_code == 403
