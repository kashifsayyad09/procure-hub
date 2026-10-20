from datetime import UTC

import pytest

from app.models import Role


def test_protected_endpoints_reject_anonymous(client):
    for method, url in [("get", "/api/v1/users"), ("post", "/api/v1/users"), ("get", "/api/v1/users/x"), ("patch", "/api/v1/users/x"), ("get", "/api/v1/auth/me")]:
        assert getattr(client, method)(url).status_code == 401, url


@pytest.mark.parametrize("role", [r for r in Role if r is not Role.ADMIN])
def test_only_administrators_can_manage_users(client, make_user, auth_headers, role):
    make_user(f"{role.value}@example.com", role)
    h = auth_headers(f"{role.value}@example.com")
    assert client.get("/api/v1/users", headers=h).status_code == 403
    body = {"email": "new@example.com", "full_name": "New", "role": "employee", "password": "Correct-horse-42"}
    assert client.post("/api/v1/users", headers=h, json=body).status_code == 403
    assert client.patch("/api/v1/users/anything", headers=h, json={"role": "admin"}).status_code == 403


def test_user_cannot_escalate_own_role(client, make_user, auth_headers):
    u = make_user("emp@example.com")
    r = client.patch(f"/api/v1/users/{u.id}", headers=auth_headers("emp@example.com"), json={"role": "admin"})
    assert r.status_code == 403


def test_forged_token_with_admin_role_is_rejected(client, make_user, settings):
    from datetime import datetime, timedelta

    import jwt
    u = make_user("emp@example.com")
    now = datetime.now(UTC)
    forged = jwt.encode({"iss": settings.jwt_issuer, "aud": settings.jwt_audience, "sub": u.id, "role": "admin", "typ": "access", "iat": now, "exp": now + timedelta(minutes=5)}, "wrong-secret-wrong-secret-wrong-secret", algorithm="HS256")
    assert client.get("/api/v1/users", headers={"Authorization": f"Bearer {forged}"}).status_code == 401


def test_role_claim_in_a_valid_token_is_not_trusted_over_the_database(client, make_user, auth_headers, db):
    admin = make_user("admin@example.com", Role.ADMIN)
    h = auth_headers("admin@example.com")  # token says admin
    assert client.get("/api/v1/users", headers=h).status_code == 200
    admin.role = Role.EMPLOYEE.value
    db.commit()
    assert client.get("/api/v1/users", headers=h).status_code == 403  # demotion applies at once


def test_suspended_users_existing_token_stops_working(client, make_user, auth_headers, db):
    u = make_user("emp@example.com")
    h = auth_headers("emp@example.com")
    assert client.get("/api/v1/auth/me", headers=h).status_code == 200
    u.is_active = False
    db.commit()
    assert client.get("/api/v1/auth/me", headers=h).status_code == 401


def test_deleted_user_token_stops_working(client, make_user, auth_headers, db):
    u = make_user("emp@example.com")
    h = auth_headers("emp@example.com")
    db.delete(u)
    db.commit()
    assert client.get("/api/v1/auth/me", headers=h).status_code == 401


def test_sql_injection_in_login_and_search_is_inert(client, make_user, auth_headers):
    make_user("admin@example.com", Role.ADMIN)
    r = client.post("/api/v1/auth/login", json={"email": "admin@example.com", "password": "' OR '1'='1"})
    assert r.status_code == 401
    h = auth_headers("admin@example.com")
    assert client.get("/api/v1/users", headers=h, params={"q": "' OR 1=1 --"}).json()["total"] == 0
