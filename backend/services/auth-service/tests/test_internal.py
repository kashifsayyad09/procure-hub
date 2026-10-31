from procurehub_common.service_auth import create_service_token

from app.models import Role

URL = "/internal/v1/users"
SVC = {"Authorization": f"Bearer {create_service_token('i' * 40, 'approval-service')}"}


def test_internal_users_requires_a_service_token(client, make_user, auth_headers):
    make_user("mgr@example.com", Role.MANAGER)
    assert client.get(URL).status_code == 401
    assert client.get(URL, headers={"Authorization": "Bearer nope"}).status_code == 401
    assert client.get(URL, headers=auth_headers("mgr@example.com")).status_code == 401  # a signed-in user's token is not a service token
    other = {"Authorization": f"Bearer {create_service_token('i' * 40, 'purchase-request-service')}"}
    assert client.get(URL, headers=other).status_code == 401  # only the approval service may ask
    wrong_key = {"Authorization": f"Bearer {create_service_token('z' * 40, 'approval-service')}"}
    assert client.get(URL, headers=wrong_key).status_code == 401


def test_lists_only_active_managers_without_secrets(client, make_user):
    make_user("a@example.com", Role.MANAGER, name="Zed Manager")
    make_user("b@example.com", Role.MANAGER, name="Amy Manager")
    make_user("c@example.com", Role.MANAGER, active=False, name="Gone Manager")
    make_user("d@example.com", Role.EMPLOYEE, name="Eve Employee")
    r = client.get(URL, headers=SVC)
    assert r.status_code == 200
    assert [u["full_name"] for u in r.json()] == ["Amy Manager", "Zed Manager"]
    assert set(r.json()[0]) == {"id", "full_name", "email"} and "hash" not in r.text and "password" not in r.text
    assert [u["full_name"] for u in client.get(URL, headers=SVC, params={"role": "employee"}).json()] == ["Eve Employee"]
    assert client.get(URL, headers=SVC, params={"role": "boss"}).status_code == 422


def test_internal_routes_are_hidden_and_disabled_when_not_configured(client, settings, engine):
    from fastapi.testclient import TestClient

    from app.config import Settings
    from app.main import create_app
    assert "/internal/v1/users" not in client.get("/openapi.json").json()["paths"]
    off = Settings(database_url="sqlite://", jwt_secret="x" * 40, log_level="CRITICAL")
    assert TestClient(create_app(off, engine)).get(URL, headers=SVC).status_code == 503
