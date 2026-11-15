import io
import os
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect

from app.config import Settings
from app.main import create_app
from app.models import Base
from tests.conftest import INTERNAL, SECRET

ROOT = Path(__file__).resolve().parent.parent
TABLES = {"rfqs", "rfq_items", "rfq_invitations", "quotations", "quotation_items", "evaluations", "selections", "rfq_history", "quotation_events", "number_sequences"}


def test_health_endpoints(client):
    assert client.get("/health/live").json() == {"status": "ok"}
    assert client.get("/health/ready").json() == {"status": "ok"}


def test_readiness_fails_when_the_database_is_down(settings):
    assert TestClient(create_app(settings, create_engine("sqlite:////nonexistent-dir/x.db"))).get("/health/ready").status_code == 503


def test_openapi_documents_the_api_and_hides_the_internal_routes(client):
    paths = client.get("/openapi.json").json()["paths"]
    for p in ("/api/v1/rfqs", "/api/v1/rfqs/{rfq_id}/comparison", "/api/v1/rfqs/{rfq_id}/selection", "/api/v1/rfqs/invited", "/api/v1/quotations", "/api/v1/quotations/{quotation_id}/submit"):
        assert p in paths, p
    assert not [p for p in paths if p.startswith("/internal")]


def test_docs_can_be_switched_off(engine):
    app = TestClient(create_app(Settings(database_url="sqlite://", jwt_secret=SECRET, docs_enabled=False, log_level="CRITICAL"), engine))
    assert app.get("/docs").status_code == 404 and app.get("/openapi.json").status_code == 404


def test_configuration_is_validated():
    with pytest.raises(ValueError, match="at least 32"):
        Settings(database_url="sqlite://", jwt_secret="short")
    with pytest.raises(ValueError, match="at least 32"):
        Settings(database_url="sqlite://", jwt_secret=SECRET, internal_jwt_secret="short")
    with pytest.raises(ValueError, match="INTERNAL_JWT_SECRET is required"):
        Settings(database_url="sqlite://", jwt_secret=SECRET, vendor_service_url="http://vendor")
    assert Settings(database_url="sqlite://", jwt_secret=SECRET, internal_jwt_secret=INTERNAL, vendor_service_url="http://vendor").min_deadline_hours == 1


def test_responses_carry_a_request_id(client):
    assert client.get("/health/live", headers={"X-Request-ID": "abc-123"}).headers["X-Request-ID"] == "abc-123"


def test_errors_never_leak_internals(client, make_rfq):
    from tests.conftest import PROC
    r = client.get("/api/v1/rfqs/%27%20OR%201%3D1--", headers=PROC)
    assert r.status_code == 404 and "sql" not in r.text.lower() and "Traceback" not in r.text
    r = client.get("/api/v1/rfqs?q=%27%3B%20DROP%20TABLE%20rfqs%3B--", headers=PROC)
    assert r.status_code == 200 and r.json()["total"] == 0
    make_rfq()
    assert client.get("/api/v1/rfqs", headers=PROC).json()["total"] == 1  # the table is still there


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
    assert TABLES <= set(inspect(eng).get_table_names())
    with eng.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == [], diff  # models and migration have not drifted apart
    command.downgrade(cfg, "base")
    assert set(inspect(eng).get_table_names()) == {"alembic_version"}


def test_migration_generates_valid_mysql_ddl_with_the_guarding_indexes(monkeypatch):
    cfg = _cfg("mysql+pymysql://u:p@localhost/quotation_db", monkeypatch)
    buf = io.StringIO()
    cfg.output_buffer = buf
    command.upgrade(cfg, "head", sql=True)
    sql = buf.getvalue()
    for needle in ("CREATE TABLE rfqs", "CREATE TABLE quotations", "CREATE TABLE selections", "UNIQUE (active_request_id)", "UNIQUE (active_rfq_id)", "uq_quotation_rfq_vendor",
                   "uq_invitation_rfq_vendor", "uq_quotation_item", "NUMERIC(14, 4)", "NUMERIC(14, 2)", "ON DELETE CASCADE"):
        assert needle in sql, needle
    assert "FLOAT" not in sql.upper() and "DOUBLE" not in sql.upper()  # money is never floating point
    assert "REFERENCES vendors" not in sql and "REFERENCES purchase_requests" not in sql  # no foreign keys into other services' databases


@pytest.mark.skipif(not os.environ.get("TEST_DATABASE_URL"), reason="needs TEST_DATABASE_URL pointing at a scratch MySQL database")
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
    with eng.begin() as conn:
        conn.exec_driver_sql("DROP TABLE IF EXISTS alembic_version")
