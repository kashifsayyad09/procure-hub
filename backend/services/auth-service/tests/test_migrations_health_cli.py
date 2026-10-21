import io
import os
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect, select

from app.cli import create_admin
from app.database import make_session_factory
from app.models import Base, Role, User

ROOT = Path(__file__).resolve().parent.parent


def _cfg(url, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", url)
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    return cfg


def test_migration_matches_models_and_downgrades(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'm.db'}"
    cfg = _cfg(url, monkeypatch)
    command.upgrade(cfg, "head")
    eng = create_engine(url)
    assert {"users", "refresh_tokens", "alembic_version"} <= set(inspect(eng).get_table_names())
    with eng.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == [], diff  # models and migration have not drifted apart
    command.downgrade(cfg, "base")
    assert set(inspect(eng).get_table_names()) == {"alembic_version"}


def test_migration_generates_valid_mysql_ddl_offline(monkeypatch):
    cfg = _cfg("mysql+pymysql://u:p@localhost/auth_db", monkeypatch)
    buf = io.StringIO()
    cfg.output_buffer = buf
    command.upgrade(cfg, "head", sql=True)
    sql = buf.getvalue()
    for needle in ("CREATE TABLE users", "CREATE TABLE refresh_tokens", "CREATE UNIQUE INDEX ix_users_email", "ON DELETE CASCADE", "BOOL"):
        assert needle in sql, needle


def test_health_endpoints(client):
    assert client.get("/health/live").json() == {"status": "ok"}
    assert client.get("/health/ready").json() == {"status": "ok"}


def test_readiness_fails_when_database_is_down(settings):
    from fastapi.testclient import TestClient

    from app.main import create_app
    bad = create_engine("sqlite:////nonexistent-dir/x.db")
    assert TestClient(create_app(settings, bad)).get("/health/ready").status_code == 503


def test_openapi_documents_the_api(client):
    paths = client.get("/openapi.json").json()["paths"]
    assert "/api/v1/auth/login" in paths and "/api/v1/users" in paths


def test_docs_can_be_disabled():
    from fastapi.testclient import TestClient

    from app.config import Settings
    from app.main import create_app
    s = Settings(database_url="sqlite://", jwt_secret="x" * 40, docs_enabled=False)
    assert TestClient(create_app(s, create_engine("sqlite://"))).get("/docs").status_code == 404


def test_create_admin_cli(engine, monkeypatch):
    sf = make_session_factory(engine)
    uid = create_admin("Boss@Example.com", "The Boss", "Correct-horse-42", sf)
    with sf() as db:
        u = db.scalar(select(User).where(User.id == uid))
        assert u.role == Role.ADMIN.value and u.email == "boss@example.com" and u.password_hash.startswith("$argon2id$")
    with pytest.raises(SystemExit):
        create_admin("boss@example.com", "Dup", "Correct-horse-42", sf)
    with pytest.raises(SystemExit):
        create_admin("other@example.com", "Weak", "weak", sf)


def test_settings_require_secret_from_environment(monkeypatch):
    monkeypatch.delenv("JWT_SECRET", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    from pydantic import ValidationError

    from app.config import Settings
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_database_url_survives_special_characters_in_the_password():
    from sqlalchemy import create_engine

    from app.dburl import resolve_database_url

    for pw in ["Pass@word1", "a:b/c#d1", "p%40ss", "sp ace1", "q'uote\"1", "100%$ure!"]:
        env = {"DB_HOST": "mysql", "DB_NAME": "auth_db", "DB_USER": "auth_svc", "DB_PASSWORD": pw}
        url = create_engine(resolve_database_url(env=env)).url
        assert (url.host, url.port, url.username, url.password, url.database) == ("mysql", 3306, "auth_svc", pw, "auth_db")
        # and it survives being rendered and parsed again, as Alembic offline mode does
        from sqlalchemy.engine import make_url
        assert make_url(url.render_as_string(hide_password=False)).password == pw


def test_database_url_precedence_and_errors():
    from app.dburl import resolve_database_url

    assert resolve_database_url("sqlite://", env={"DATABASE_URL": "other"}) == "sqlite://"
    assert resolve_database_url(env={"DATABASE_URL": "sqlite://"}) == "sqlite://"
    with pytest.raises(RuntimeError, match="DB_PASSWORD"):
        resolve_database_url(env={"DB_HOST": "h", "DB_NAME": "n", "DB_USER": "u"})


@pytest.mark.skipif(not os.environ.get("TEST_DATABASE_URL"), reason="set TEST_DATABASE_URL to a scratch MySQL database")
def test_migration_on_a_real_mysql_server(monkeypatch):
    url = os.environ["TEST_DATABASE_URL"]
    eng = create_engine(url)
    Base.metadata.drop_all(eng)
    with eng.begin() as conn:
        conn.exec_driver_sql("DROP TABLE IF EXISTS alembic_version")
    cfg = _cfg(url, monkeypatch)
    command.upgrade(cfg, "head")
    with eng.connect() as conn:
        assert compare_metadata(MigrationContext.configure(conn), Base.metadata) == []
    command.downgrade(cfg, "base")
    assert set(inspect(eng).get_table_names()) <= {"alembic_version"}
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")
