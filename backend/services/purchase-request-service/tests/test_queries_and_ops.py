import io
import os
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect

from app.models import Base, PurchaseRequest
from tests.conftest import headers, payload

URL = "/api/v1/purchase-requests"
ROOT = Path(__file__).resolve().parent.parent


def _seed(client, db):
    ids = {}
    spec = [("Office chairs", "high", "5000", "Facilities"), ("Server racks", "urgent", "150000", "IT"), ("Printer toner", "low", "1200", "Admin"), ("Standing desks", "normal", "42000", "Facilities")]
    for title, prio, price, dept in spec:
        r = client.post(URL, headers=headers(), json=payload(title=title, priority=prio, department=dept, items=[{"description": title, "quantity": "1", "unit_price": price}]))
        ids[title] = r.json()["id"]
    client.post(f"{URL}/{ids['Server racks']}/submit", headers=headers())
    client.post(f"{URL}/{ids['Printer toner']}/submit", headers=headers())
    return ids


def test_filters_search_sort_and_paging(client, db):
    ids = _seed(client, db)
    h = headers()
    get = lambda **p: client.get(URL, headers=h, params=p).json()  # noqa: E731
    assert get()["total"] == 4
    assert {i["title"] for i in get(status="submitted")["items"]} == {"Server racks", "Printer toner"}
    assert [i["title"] for i in get(priority="urgent")["items"]] == ["Server racks"]
    assert [i["title"] for i in get(q="DESK")["items"]] == ["Standing desks"]
    assert get(q="pr-")["total"] == 4 and get(q="alice")["total"] == 4 and get(q="zzz")["total"] == 0
    assert [i["title"] for i in get(sort="total_amount", order="desc")["items"]][:2] == ["Server racks", "Standing desks"]
    assert [i["title"] for i in get(sort="total_amount", order="asc")["items"]][0] == "Printer toner"
    p1, p2 = get(page_size=3, page=1), get(page_size=3, page=2)
    assert len(p1["items"]) == 3 and len(p2["items"]) == 1 and p1["total"] == 4
    assert not {i["id"] for i in p1["items"]} & {i["id"] for i in p2["items"]}
    today = date.today()
    assert get(created_from=str(today), created_to=str(today))["total"] == 4
    assert get(created_to=str(today - timedelta(days=1)))["total"] == 0
    assert get(created_from=str(today + timedelta(days=1)))["total"] == 0
    assert ids  # seeded


def test_list_validation_and_limits(client):
    h = headers()
    assert client.get(URL, headers=h, params={"page_size": 101}).status_code == 422
    assert client.get(URL, headers=h, params={"page": 0}).status_code == 422
    assert client.get(URL, headers=h, params={"sort": "requester_id"}).status_code == 422  # only listed columns can be sorted
    assert client.get(URL, headers=h, params={"status": "bogus"}).status_code == 422


def test_wildcards_in_search_are_literal(client, create):
    create(title="100% cotton towels")
    create(title="Plain towels")
    h = headers()
    assert client.get(URL, headers=h, params={"q": "100%"}).json()["total"] == 1
    assert client.get(URL, headers=h, params={"q": "%"}).json()["total"] == 1
    assert client.get(URL, headers=h, params={"q": "_"}).json()["total"] == 0


def test_summary_counts_value_and_months(client, db):
    _seed(client, db)
    s = client.get(f"{URL}/summary", headers=headers()).json()
    assert s["counts"] == {"draft": 2, "submitted": 2, "approved": 0, "rejected": 0, "cancelled": 0}
    assert s["open_value"] == {"INR": "151200.00"}
    assert len(s["monthly"]) == 6 and s["monthly"][-1] == {"month": date.today().strftime("%Y-%m"), "count": 4}
    assert all(m["count"] == 0 for m in s["monthly"][:-1])


def test_summary_never_adds_different_currencies(client):
    for cur in ("INR", "USD"):
        r = client.post(URL, headers=headers(), json=payload(currency=cur, items=[{"description": "x", "quantity": "1", "unit_price": "100"}])).json()
        client.post(f"{URL}/{r['id']}/submit", headers=headers())
    assert client.get(f"{URL}/summary", headers=headers()).json()["open_value"] == {"INR": "100.00", "USD": "100.00"}


def test_summary_counts_old_requests_in_the_right_month(client, create, db):
    r = create()
    row = db.get(PurchaseRequest, r["id"])
    row.created_at = datetime.now() - timedelta(days=75)
    db.commit()
    months = client.get(f"{URL}/summary", headers=headers()).json()["monthly"]
    assert sum(m["count"] for m in months) == 1 and months[-1]["count"] == 0


# ---- service basics -----------------------------------------------------------------------------------
def test_health_and_openapi(client):
    assert client.get("/health/live").json() == {"status": "ok"}
    assert client.get("/health/ready").json() == {"status": "ok"}
    r = client.get("/health/live", headers={"X-Request-ID": "trace-123"})
    assert r.headers["x-request-id"] == "trace-123"
    assert "/api/v1/purchase-requests" in client.get("/openapi.json").json()["paths"]


def test_readiness_fails_when_database_is_down(settings):
    from fastapi.testclient import TestClient

    from app.main import create_app
    assert TestClient(create_app(settings, create_engine("sqlite:////nonexistent-dir/x.db"))).get("/health/ready").status_code == 503


def test_service_refuses_to_start_without_a_strong_secret(monkeypatch):
    from pydantic import ValidationError

    from app.config import Settings
    monkeypatch.delenv("JWT_SECRET", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)
    with pytest.raises(ValidationError):
        Settings(jwt_secret="short")


def test_service_does_not_depend_on_another_services_code():
    import re
    for f in (ROOT / "app").rglob("*.py"):
        text = f.read_text()
        assert not re.search(r"^\s*(from|import)\s+(auth_service|approval|vendor)", text, re.M), f


# ---- migrations --------------------------------------------------------------------------------------
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
    assert {"purchase_requests", "purchase_request_items", "purchase_request_documents", "purchase_request_history", "number_sequences"} <= set(inspect(eng).get_table_names())
    with eng.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == [], diff
    command.downgrade(cfg, "base")
    assert set(inspect(eng).get_table_names()) == {"alembic_version"}


def test_migration_generates_valid_mysql_ddl_offline(monkeypatch):
    cfg = _cfg("mysql+pymysql://u:p@localhost/purchase_request_db", monkeypatch)
    buf = io.StringIO()
    cfg.output_buffer = buf
    command.upgrade(cfg, "head", sql=True)
    sql = buf.getvalue()
    for needle in ("CREATE TABLE purchase_requests", "total_amount NUMERIC(14, 2) NOT NULL", "quantity NUMERIC(12, 3) NOT NULL", "ON DELETE CASCADE",
                   "UNIQUE (number)", "number VARCHAR(20) NOT NULL"):  # NUMERIC is an exact fixed-point type in MySQL, never floating point
        assert needle in sql, needle


MYSQL = pytest.mark.skipif(not os.environ.get("TEST_DATABASE_URL"), reason="set TEST_DATABASE_URL to a scratch MySQL database")


@MYSQL
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
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")


@MYSQL
def test_concurrent_creates_get_unique_gap_free_numbers(app):
    from concurrent.futures import ThreadPoolExecutor

    from procurehub_common.tokens import TokenClaims

    from app import service
    from app.schemas import RequestIn
    me = TokenClaims(sub="emp-a", role="employee", name="Alice", email="a@example.com")

    def make(_):
        with app.state.session_factory() as s:
            return service.create(s, me, RequestIn(title="Concurrent request")).number

    with ThreadPoolExecutor(max_workers=12) as pool:
        numbers = list(pool.map(make, range(36)))
    assert len(set(numbers)) == 36
    year = date.today().year
    assert sorted(numbers) == [f"PR-{year}-{i:06d}" for i in range(1, 37)]
