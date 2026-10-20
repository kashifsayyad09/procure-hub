from datetime import timedelta

from sqlalchemy import select

from app.models import RefreshToken, Role, User, utcnow
from tests.conftest import PASSWORD

COOKIE = "ph_refresh"


def test_login_success_returns_token_user_and_secure_cookie(client, make_user, login):
    make_user("emp@example.com", Role.EMPLOYEE)
    r = login("EMP@example.com")  # email is case-insensitive
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer" and body["expires_in"] == 900
    assert body["user"]["role"] == "employee" and "purchase_request:create" in body["user"]["permissions"]
    assert "password" not in r.text and "hash" not in r.text
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie and "path=/api/v1/auth" in cookie
    assert r.headers["cache-control"] == "no-store" and r.headers["x-request-id"]


def test_wrong_password_and_unknown_email_give_the_same_answer(make_user, login):
    make_user("emp@example.com")
    a, b = login("emp@example.com", "nope-nope-nope1"), login("ghost@example.com", "nope-nope-nope1")
    assert a.status_code == b.status_code == 401 and a.json() == b.json()
    assert COOKIE not in a.headers.get("set-cookie", "")


def test_account_locks_after_repeated_failures_even_with_right_password(make_user, login):
    make_user("emp@example.com")
    for _ in range(3):
        assert login("emp@example.com", "bad-bad-bad-1").status_code == 401
    r = login("emp@example.com")
    assert r.status_code == 429 and int(r.headers["retry-after"]) > 0


def test_lock_expires_and_counter_resets(make_user, login, db):
    u = make_user("emp@example.com")
    for _ in range(3):
        login("emp@example.com", "bad-bad-bad-1")
    db.refresh(u)
    u.locked_until = utcnow() - timedelta(seconds=1)
    db.commit()
    assert login("emp@example.com").status_code == 200
    db.refresh(u)
    assert u.failed_login_attempts == 0 and u.locked_until is None


def test_suspended_user_cannot_sign_in(make_user, login):
    make_user("emp@example.com", active=False)
    assert login("emp@example.com").status_code == 403
    assert login("emp@example.com", "wrong-wrong-1").status_code == 401  # wrong password reveals nothing


def test_me_requires_a_valid_token(client, make_user, auth_headers):
    make_user("emp@example.com")
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.get("/api/v1/auth/me", headers={"Authorization": "Bearer garbage"}).status_code == 401
    r = client.get("/api/v1/auth/me", headers=auth_headers("emp@example.com"))
    assert r.status_code == 200 and r.json()["email"] == "emp@example.com"


def test_refresh_rotates_and_stores_only_hashes(client, make_user, login, db):
    make_user("emp@example.com")
    login("emp@example.com")
    first = client.cookies.get(COOKIE)
    r = client.post("/api/v1/auth/refresh")
    assert r.status_code == 200 and r.json()["access_token"]
    second = client.cookies.get(COOKIE)
    assert second and second != first
    rows = db.scalars(select(RefreshToken)).all()
    assert len(rows) == 2 and first not in {r.token_hash for r in rows}
    assert sum(1 for r in rows if r.revoked_at is None) == 1
    assert len({r.family_id for r in rows}) == 1


def test_refresh_without_cookie_is_denied(client):
    r = client.post("/api/v1/auth/refresh")
    assert r.status_code == 401


def test_replayed_refresh_token_revokes_the_whole_family(client, make_user, login, db, app):
    make_user("emp@example.com")
    login("emp@example.com")
    stolen = client.cookies.get(COOKIE)
    client.post("/api/v1/auth/refresh")  # legitimate rotation
    for row in db.scalars(select(RefreshToken)).all():  # age the rotation beyond the grace window
        if row.revoked_at:
            row.revoked_at = utcnow() - timedelta(minutes=5)
    db.commit()
    client.cookies.clear()
    client.cookies.set(COOKIE, stolen, path="/api/v1/auth")
    assert client.post("/api/v1/auth/refresh").status_code == 401
    db.expire_all()
    assert all(r.revoked_at for r in db.scalars(select(RefreshToken)).all())


def test_near_simultaneous_refresh_is_tolerated_without_revoking(client, make_user, login, db):
    make_user("emp@example.com")
    login("emp@example.com")
    old = client.cookies.get(COOKIE)
    assert client.post("/api/v1/auth/refresh").status_code == 200
    current = client.cookies.get(COOKIE)
    client.cookies.clear()
    client.cookies.set(COOKIE, old, path="/api/v1/auth")
    assert client.post("/api/v1/auth/refresh").status_code == 401
    db.expire_all()
    assert sum(1 for r in db.scalars(select(RefreshToken)).all() if r.revoked_at is None) == 1  # newest still valid
    client.cookies.clear()
    client.cookies.set(COOKIE, current, path="/api/v1/auth")
    assert client.post("/api/v1/auth/refresh").status_code == 200


def test_expired_refresh_token_denied(client, make_user, login, db):
    make_user("emp@example.com")
    login("emp@example.com")
    row = db.scalar(select(RefreshToken))
    row.expires_at = utcnow() - timedelta(seconds=1)
    db.commit()
    assert client.post("/api/v1/auth/refresh").status_code == 401


def test_logout_revokes_session_and_clears_cookie(client, make_user, login):
    make_user("emp@example.com")
    login("emp@example.com")
    r = client.post("/api/v1/auth/logout")
    assert r.status_code == 204 and "max-age=0" in r.headers["set-cookie"].lower()
    assert client.post("/api/v1/auth/refresh").status_code == 401


def test_logout_without_session_is_harmless(client):
    assert client.post("/api/v1/auth/logout").status_code == 204


def test_logout_all_revokes_every_device(client, make_user, login, auth_headers, app):
    make_user("emp@example.com")
    login("emp@example.com")
    from fastapi.testclient import TestClient
    other = TestClient(app)
    other.post("/api/v1/auth/login", json={"email": "emp@example.com", "password": PASSWORD})
    h = auth_headers("emp@example.com")
    assert client.post("/api/v1/auth/logout-all", headers=h).status_code == 204
    assert client.post("/api/v1/auth/refresh").status_code == 401
    assert other.post("/api/v1/auth/refresh").status_code == 401


def test_change_password(client, make_user, login, auth_headers):
    make_user("emp@example.com")
    h = auth_headers("emp@example.com")
    url = "/api/v1/auth/change-password"
    assert client.post(url, headers=h, json={"current_password": "wrong", "new_password": "Another-pass-77"}).status_code == 400
    assert client.post(url, headers=h, json={"current_password": PASSWORD, "new_password": "short"}).status_code == 422
    assert client.post(url, headers=h, json={"current_password": PASSWORD, "new_password": "Another-pass-77"}).status_code == 204
    assert client.post("/api/v1/auth/refresh").status_code == 401  # sessions ended
    assert login("emp@example.com").status_code == 401
    assert login("emp@example.com", "Another-pass-77").status_code == 200


def test_old_hash_is_upgraded_on_login(client, make_user, login, db):
    from argon2 import PasswordHasher
    u = make_user("emp@example.com")
    u.password_hash = PasswordHasher(time_cost=1, memory_cost=8, parallelism=1).hash(PASSWORD)
    db.commit()
    assert login("emp@example.com").status_code == 200
    db.refresh(u)
    assert u.password_hash != "" and db.get(User, u.id).password_hash.startswith("$argon2id$")
