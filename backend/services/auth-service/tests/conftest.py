import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.main import create_app
from app.models import Base, Role, User
from app.security import hash_password

PASSWORD = "Correct-horse-42"


@pytest.fixture
def settings():
    return Settings(database_url="sqlite://", jwt_secret="x" * 40, cookie_secure=False, max_failed_logins=3, log_level="CRITICAL")


@pytest.fixture
def engine():
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    return eng


@pytest.fixture
def app(settings, engine):
    return create_app(settings, engine)


@pytest.fixture
def client(app):
    return TestClient(app, base_url="http://testserver")


@pytest.fixture
def db(app):
    with app.state.session_factory() as session:
        yield session


@pytest.fixture
def make_user(db):
    def _make(email="emp@example.com", role=Role.EMPLOYEE, active=True, name="Test User"):
        u = User(email=email, full_name=name, role=role.value, is_active=active, password_hash=hash_password(PASSWORD))
        db.add(u)
        db.commit()
        return u
    return _make


@pytest.fixture
def login(client):
    def _login(email, password=PASSWORD):
        return client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return _login


@pytest.fixture
def auth_headers(login):
    def _h(email):
        r = login(email)
        assert r.status_code == 200, r.text
        return {"Authorization": f"Bearer {r.json()['access_token']}"}
    return _h
