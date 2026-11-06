import pytest

from tests.conftest import ADMIN, PROC, URL, VENDOR_A, headers, make_token, payload


def _endpoints(vid="some-id"):
    return [("get", URL, None), ("post", URL, payload()), ("post", f"{URL}/onboard", payload()), ("get", f"{URL}/summary", None), ("get", f"{URL}/categories", None),
            ("get", f"{URL}/me", None), ("get", f"{URL}/{vid}", None), ("put", f"{URL}/{vid}", payload() | {"version": 1}), ("post", f"{URL}/{vid}/submit", None),
            ("post", f"{URL}/{vid}/verify", {"version": 1}), ("post", f"{URL}/{vid}/reject", {"version": 1, "reason": "abc"}),
            ("post", f"{URL}/{vid}/suspend", {"version": 1, "reason": "abc"}), ("post", f"{URL}/{vid}/reinstate", {"version": 1})]


def _call(client, method, url, body, h=None):
    kw = {"headers": h} if h else {}
    if body is not None:
        kw["json"] = body
    return getattr(client, method)(url, **kw)


def test_every_endpoint_rejects_anonymous_callers(client):
    for method, url, body in _endpoints():
        assert _call(client, method, url, body).status_code == 401, (method, url)


@pytest.mark.parametrize("bad", [
    {"Authorization": "Bearer garbage"}, {"Authorization": "Basic abc"}, headers(secret="y" * 40), headers(aud="other"), headers(iss="other"), headers(ttl=-5),
    headers(typ="refresh"), {"Authorization": f"Bearer {make_token(alg='HS512')}"},
])
def test_invalid_tokens_are_rejected(client, bad):
    assert client.get(URL + "/me", headers=bad).status_code == 401
    assert client.get(URL, headers=bad).status_code == 401


def test_unsigned_token_is_rejected(client):
    import jwt
    forged = jwt.encode({"sub": "x", "role": "admin", "typ": "access", "iss": "procurehub-auth", "aud": "procurehub", "iat": 1, "exp": 9999999999}, None, algorithm="none")
    assert client.get(URL, headers={"Authorization": f"Bearer {forged}"}).status_code == 401


@pytest.mark.parametrize("role", ["employee", "manager", "finance"])
def test_roles_without_vendor_permissions_are_forbidden_everywhere(client, register, role):
    v = register()
    for method, url, body in _endpoints(v["id"]):
        assert _call(client, method, url, body, headers(role, f"{role}-1")).status_code == 403, (role, method, url)


def test_unknown_role_in_a_valid_token_gets_nothing(client):
    assert client.get(URL, headers=headers("superuser")).status_code == 403


def test_a_vendor_user_cannot_browse_the_directory_or_use_staff_endpoints(client, register):
    v = register()
    for method, url, body in [("get", URL, None), ("get", f"{URL}/summary", None), ("post", f"{URL}/onboard", payload()),
                              ("post", f"{URL}/{v['id']}/verify", {"version": 1}), ("post", f"{URL}/{v['id']}/suspend", {"version": 1, "reason": "abc"})]:
        assert _call(client, method, url, body, VENDOR_A).status_code == 403, (method, url)


@pytest.mark.parametrize("h", [PROC, ADMIN])
def test_staff_do_not_have_a_vendor_profile_of_their_own(client, h):
    assert client.get(f"{URL}/me", headers=h).status_code == 403
    assert client.post(URL, headers=h, json=payload()).status_code == 403


@pytest.mark.parametrize("h", [PROC, ADMIN])
def test_staff_can_browse_and_read(client, register, h):
    v = register()
    assert client.get(URL, headers=h).json()["total"] == 1
    assert client.get(f"{URL}/{v['id']}", headers=h).status_code == 200
    assert client.get(f"{URL}/summary", headers=h).status_code == 200
    assert client.get(f"{URL}/categories", headers=h).status_code == 200


def test_the_role_comes_from_the_signed_token_not_from_a_header_or_query(client, register):
    register()
    forged = {**VENDOR_A, "X-Role": "admin"}
    assert client.get(URL + "?role=admin", headers=forged).status_code == 403


def test_vendor_can_list_categories(client):
    r = client.get(f"{URL}/categories", headers=VENDOR_A)
    assert r.status_code == 200 and {"id": "it_hardware", "label": "IT hardware"} in r.json() and len(r.json()) == 10
