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
from tests.conftest import ADMIN, PROC, SECRET, URL, VENDOR_A, VENDOR_B, payload, svc

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def directory(client):
    """Five vendors in different states, registered by staff and by vendor users."""
    made = {}

    def reg(key, h, path=URL, **over):
        r = client.post(path, headers=h, json=payload(**over))
        assert r.status_code == 201, r.text
        made[key] = r.json()

    reg("alpha", VENDOR_A, legal_name="Alpha Hardware Ltd", tax_id="ALPHA00001", city="Pune", categories=["it_hardware"])
    reg("bravo", VENDOR_B, legal_name="Bravo Furniture LLP", tax_id="BRAVO00001", city="Delhi", categories=["furniture", "office_supplies"])
    reg("charlie", PROC, f"{URL}/onboard", legal_name="Charlie Logistics", tax_id="CHARL00001", city="Mumbai", country="US", categories=["logistics"])
    reg("delta", PROC, f"{URL}/onboard", legal_name="100% Delta_Works", tax_id="DELTA00001", city="Chennai", categories=["it_hardware", "software"])
    reg("echo", PROC, f"{URL}/onboard", legal_name="Echo Services", tax_id="ECHO000001", city="Pune", categories=["professional_services"])
    for k in ("alpha", "bravo"):  # submit and verify two of them
        client.post(f"{URL}/{made[k]['id']}/submit", headers=VENDOR_A if k == "alpha" else VENDOR_B)
        v = client.get(f"{URL}/{made[k]['id']}", headers=PROC).json()
        client.post(f"{URL}/{v['id']}/verify", headers=PROC, json={"version": v["version"]})
    c = client.post(f"{URL}/{made['charlie']['id']}/submit", headers=PROC).json()
    made["charlie"] = c
    return made


def _names(r):
    return [v["legal_name"] for v in r.json()["items"]]


def test_directory_defaults_to_name_order(client, directory):
    r = client.get(URL, headers=PROC)
    assert r.json()["total"] == 5 and _names(r) == sorted(_names(r))


def test_filter_by_status_category_and_country(client, directory):
    assert _names(client.get(URL + "?status=verified", headers=PROC)) == ["Alpha Hardware Ltd", "Bravo Furniture LLP"]
    assert _names(client.get(URL + "?status=pending", headers=PROC)) == ["Charlie Logistics"]
    assert _names(client.get(URL + "?status=draft", headers=PROC)) == ["100% Delta_Works", "Echo Services"]
    assert _names(client.get(URL + "?category=it_hardware", headers=PROC)) == ["100% Delta_Works", "Alpha Hardware Ltd"]
    assert _names(client.get(URL + "?country=us", headers=PROC)) == ["Charlie Logistics"]
    assert _names(client.get(URL + "?category=it_hardware&status=verified", headers=PROC)) == ["Alpha Hardware Ltd"]
    assert client.get(URL + "?category=unknown", headers=PROC).json()["total"] == 0
    assert client.get(URL + "?status=bogus", headers=PROC).status_code == 422


def test_search_matches_name_number_tax_id_and_city_and_treats_wildcards_literally(client, directory):
    assert _names(client.get(URL + "?q=bravo", headers=PROC)) == ["Bravo Furniture LLP"]
    assert _names(client.get(URL + "?q=pune", headers=PROC)) == ["Alpha Hardware Ltd", "Echo Services"]
    assert _names(client.get(URL + "?q=ECHO000001", headers=PROC)) == ["Echo Services"]
    assert _names(client.get(f"{URL}?q={directory['delta']['number']}", headers=PROC)) == ["100% Delta_Works"]
    assert _names(client.get(URL + "?q=100%25", headers=PROC)) == ["100% Delta_Works"]
    assert client.get(URL + "?q=%25", headers=PROC).json()["total"] == 1  # a literal percent sign, not "match everything"
    assert client.get(URL + "?q=_", headers=PROC).json()["total"] == 1
    assert client.get(URL + "?q=zzz", headers=PROC).json()["total"] == 0


def test_sorting_and_paging(client, directory):
    desc = client.get(URL + "?sort=legal_name&order=desc", headers=PROC)
    assert _names(desc) == sorted(_names(desc), reverse=True)
    p1 = client.get(URL + "?page=1&page_size=2", headers=PROC).json()
    p3 = client.get(URL + "?page=3&page_size=2", headers=PROC).json()
    assert p1["total"] == 5 and len(p1["items"]) == 2 and len(p3["items"]) == 1
    seen = [v["id"] for n in (1, 2, 3) for v in client.get(f"{URL}?page={n}&page_size=2", headers=PROC).json()["items"]]
    assert len(set(seen)) == 5
    for bad in ("page=0", "page_size=0", "page_size=101", "sort=owner_id", "order=sideways"):
        assert client.get(f"{URL}?{bad}", headers=PROC).status_code == 422, bad


def test_list_items_are_summaries_without_private_detail(client, directory):
    item = client.get(URL, headers=PROC).json()["items"][0]
    assert {"id", "number", "legal_name", "status", "categories", "primary_contact_email", "has_account"} <= set(item)
    assert not ({"tax_id", "history", "contacts", "owner_id", "address_line1"} & set(item))


def test_summary_counts_categories_and_months(client, directory):
    s = client.get(f"{URL}/summary", headers=ADMIN).json()
    assert s["counts"] == {"draft": 2, "pending": 1, "verified": 2, "rejected": 0, "suspended": 0}
    assert {"category": "it_hardware", "count": 1} in s["verified_by_category"]
    assert sum(m["count"] for m in s["monthly"]) == 5 and len(s["monthly"]) == 6


def test_summary_of_an_empty_directory(client):
    s = client.get(f"{URL}/summary", headers=PROC).json()
    assert s["counts"] == {"draft": 0, "pending": 0, "verified": 0, "rejected": 0, "suspended": 0} and s["verified_by_category"] == []


# ---- internal API ----------------------------------------------------------------------------------
def test_internal_api_returns_references_with_status_for_an_allowed_service(client, directory):
    r = client.get(f"/internal/v1/vendors/{directory['alpha']['id']}", headers=svc())
    assert r.status_code == 200
    ref = r.json()
    assert ref["status"] == "verified" and ref["legal_name"] == "Alpha Hardware Ltd" and ref["categories"] == ["it_hardware"]
    assert ref["primary_contact_email"] == "vera@acme.example" and "tax_id" not in ref and "owner_id" not in ref
    assert client.get("/internal/v1/vendors/missing", headers=svc()).status_code == 404


def test_internal_lookup_leaves_out_unknown_ids_and_reports_status(client, directory):
    ids = [directory["alpha"]["id"], directory["echo"]["id"], "nope"]
    r = client.post("/internal/v1/vendors/lookup", headers=svc("purchase-order-service"), json={"ids": ids})
    assert r.status_code == 200
    assert {v["legal_name"]: v["status"] for v in r.json()} == {"Alpha Hardware Ltd": "verified", "Echo Services": "draft"}
    assert client.post("/internal/v1/vendors/lookup", headers=svc(), json={"ids": []}).status_code == 422
    assert client.post("/internal/v1/vendors/lookup", headers=svc(), json={"ids": ["x"] * 101}).status_code == 422


def test_internal_api_refuses_user_tokens_unknown_services_and_wrong_secrets(client, directory):
    vid = directory["alpha"]["id"]
    for h in (ADMIN, PROC, VENDOR_A, {}, svc("approval-service"), svc("random-service"), svc(secret="z" * 40), {"Authorization": "Bearer junk"}):
        assert client.get(f"/internal/v1/vendors/{vid}", headers=h).status_code == 401, h


def test_internal_api_is_disabled_without_a_secret_and_hidden_from_the_docs(engine, directory):
    off = TestClient(create_app(Settings(database_url="sqlite://", jwt_secret=SECRET, log_level="CRITICAL"), engine))
    assert off.get(f"/internal/v1/vendors/{directory['alpha']['id']}", headers=svc()).status_code == 503
    assert not [p for p in off.get("/openapi.json").json()["paths"] if p.startswith("/internal")]


# ---- service basics --------------------------------------------------------------------------------
def test_health_endpoints(client):
    assert client.get("/health/live").json() == {"status": "ok"}
    assert client.get("/health/ready").json() == {"status": "ok"}


def test_readiness_fails_when_the_database_is_down(settings):
    bad = create_engine("sqlite:////nonexistent-dir/x.db")
    assert TestClient(create_app(settings, bad)).get("/health/ready").status_code == 503


def test_openapi_documents_the_api(client):
    paths = client.get("/openapi.json").json()["paths"]
    for p in ("/api/v1/vendors", "/api/v1/vendors/me", "/api/v1/vendors/onboard", "/api/v1/vendors/{vendor_id}/verify", "/api/v1/vendors/summary"):
        assert p in paths, p


def test_docs_can_be_switched_off(engine):
    app = TestClient(create_app(Settings(database_url="sqlite://", jwt_secret=SECRET, docs_enabled=False, log_level="CRITICAL"), engine))
    assert app.get("/docs").status_code == 404 and app.get("/openapi.json").status_code == 404


def test_short_secrets_are_refused():
    with pytest.raises(ValueError, match="at least 32"):
        Settings(database_url="sqlite://", jwt_secret="short")
    with pytest.raises(ValueError, match="at least 32"):
        Settings(database_url="sqlite://", jwt_secret=SECRET, internal_jwt_secret="short")


def test_responses_carry_a_request_id(client):
    r = client.get("/health/live", headers={"X-Request-ID": "abc-123"})
    assert r.headers["X-Request-ID"] == "abc-123"


# ---- migrations ------------------------------------------------------------------------------------
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
    assert {"vendors", "vendor_categories", "vendor_contacts", "vendor_history", "vendor_events", "number_sequences"} <= set(inspect(eng).get_table_names())
    with eng.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == [], diff  # models and migration have not drifted apart
    command.downgrade(cfg, "base")
    assert set(inspect(eng).get_table_names()) == {"alembic_version"}


def test_migration_generates_valid_mysql_ddl_offline(monkeypatch):
    cfg = _cfg("mysql+pymysql://u:p@localhost/vendor_db", monkeypatch)
    buf = io.StringIO()
    cfg.output_buffer = buf
    command.upgrade(cfg, "head", sql=True)
    sql = buf.getvalue()
    for needle in ("CREATE TABLE vendors", "CREATE TABLE vendor_categories", "CREATE TABLE vendor_events", "UNIQUE (tax_id)", "UNIQUE (owner_id)", "uq_vendor_category", "ON DELETE CASCADE"):
        assert needle in sql, needle


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
