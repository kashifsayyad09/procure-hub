from app.models import Role
from tests.conftest import PASSWORD

NEW = {"email": "New.Person@example.com", "full_name": "  New Person ", "role": "vendor", "password": "Correct-horse-42"}


def _admin(make_user, auth_headers):
    a = make_user("admin@example.com", Role.ADMIN, name="Admin")
    return a, auth_headers("admin@example.com")


def test_admin_creates_user_who_can_then_sign_in(client, make_user, auth_headers, login):
    _, h = _admin(make_user, auth_headers)
    r = client.post("/api/v1/users", headers=h, json=NEW)
    assert r.status_code == 201
    body = r.json()
    assert body["email"] == "new.person@example.com" and body["full_name"] == "New Person" and body["role"] == "vendor" and "password" not in r.text
    assert login("new.person@example.com", "Correct-horse-42").json()["user"]["role"] == "vendor"


def test_create_user_validation(client, make_user, auth_headers):
    _, h = _admin(make_user, auth_headers)
    assert client.post("/api/v1/users", headers=h, json={**NEW, "password": "weak"}).status_code == 422
    assert client.post("/api/v1/users", headers=h, json={**NEW, "role": "superuser"}).status_code == 422
    assert client.post("/api/v1/users", headers=h, json={**NEW, "email": "not-an-email"}).status_code == 422
    assert client.post("/api/v1/users", headers=h, json={**NEW, "full_name": "   "}).status_code == 422
    assert client.post("/api/v1/users", headers=h, json=NEW).status_code == 201
    assert client.post("/api/v1/users", headers=h, json={**NEW, "email": "new.person@EXAMPLE.com"}).status_code == 409


def test_list_filters_search_and_pagination(client, make_user, auth_headers):
    _, h = _admin(make_user, auth_headers)
    for i in range(5):
        make_user(f"emp{i}@example.com", Role.EMPLOYEE, name=f"Employee {i}")
    make_user("mgr@example.com", Role.MANAGER, active=False, name="Pat Manager")
    page = client.get("/api/v1/users", headers=h, params={"page_size": 3}).json()
    assert page["total"] == 7 and len(page["items"]) == 3
    assert client.get("/api/v1/users", headers=h, params={"role": "employee"}).json()["total"] == 5
    assert client.get("/api/v1/users", headers=h, params={"is_active": "false"}).json()["total"] == 1
    assert client.get("/api/v1/users", headers=h, params={"q": "pat man"}).json()["items"][0]["email"] == "mgr@example.com"
    assert client.get("/api/v1/users", headers=h, params={"page_size": 1000}).status_code == 422


def test_admin_changes_role_and_suspends_which_ends_sessions(client, make_user, auth_headers, login, app):
    from fastapi.testclient import TestClient
    _, h = _admin(make_user, auth_headers)
    emp = make_user("emp@example.com")
    user_client = TestClient(app)
    user_client.post("/api/v1/auth/login", json={"email": "emp@example.com", "password": PASSWORD})
    assert client.patch(f"/api/v1/users/{emp.id}", headers=h, json={"role": "manager"}).json()["role"] == "manager"
    assert user_client.post("/api/v1/auth/refresh").status_code == 401  # must sign in again after a role change
    assert login("emp@example.com").json()["user"]["role"] == "manager"
    assert client.patch(f"/api/v1/users/{emp.id}", headers=h, json={"is_active": False}).json()["is_active"] is False
    assert login("emp@example.com").status_code == 403


def test_admin_cannot_lock_themselves_out(client, make_user, auth_headers):
    admin, h = _admin(make_user, auth_headers)
    assert client.patch(f"/api/v1/users/{admin.id}", headers=h, json={"role": "employee"}).status_code == 409
    assert client.patch(f"/api/v1/users/{admin.id}", headers=h, json={"is_active": False}).status_code == 409
    assert client.patch(f"/api/v1/users/{admin.id}", headers=h, json={"full_name": "Renamed"}).status_code == 200


def test_get_and_patch_unknown_user_404(client, make_user, auth_headers):
    _, h = _admin(make_user, auth_headers)
    assert client.get("/api/v1/users/nope", headers=h).status_code == 404
    assert client.patch("/api/v1/users/nope", headers=h, json={"full_name": "X"}).status_code == 404
