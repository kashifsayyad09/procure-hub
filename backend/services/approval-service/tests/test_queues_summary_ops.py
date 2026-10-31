import io
import os
import threading
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from fastapi import HTTPException
from procurehub_common.tokens import TokenClaims
from sqlalchemy import create_engine, inspect

from app import service
from app.models import Approval, Base, utcnow
from tests.conftest import headers, registration, svc

URL = "/api/v1/approvals"
ROOT = Path(__file__).resolve().parent.parent
M1, M2, M3 = headers(sub="mgr-1", name="Mia Manager"), headers(sub="mgr-2", name="Max Manager"), headers(sub="mgr-3", name="Mona Manager")


@pytest.fixture
def scene(client, register):
    """A1 open (50k). A2 is mgr-1's own request. A3 two-level, mgr-1 already approved level 1. A4 delegated by mgr-1 to mgr-2.
    A5 approved by mgr-1. A6 rejected by mgr-1."""
    ids = {}
    ids["A1"] = register("50000.00", request_number="PR-2026-000001", title="Standing desks", priority="normal")
    ids["A2"] = register("20000.00", request_number="PR-2026-000002", title="Own laptop", requester_id="mgr-1", requester_name="Mia Manager", priority="high")
    ids["A3"] = register("150000.00", request_number="PR-2026-000003", title="Server racks", priority="urgent")
    client.post(f"{URL}/{ids['A3']}/approve", json={}, headers=M1)
    ids["A4"] = register("30000.00", request_number="PR-2026-000004", title="Chairs")
    client.post(f"{URL}/{ids['A4']}/delegate", json={"user_id": "mgr-2"}, headers=M1)
    ids["A5"] = register("1000.00", request_number="PR-2026-000005", title="Printer toner", currency="USD")
    client.post(f"{URL}/{ids['A5']}/approve", json={}, headers=M1)
    ids["A6"] = register("5000.00", request_number="PR-2026-000006", title="100% cotton towels")
    client.post(f"{URL}/{ids['A6']}/reject", json={"reason": "not needed"}, headers=M1)
    return ids


def titles(client, who, **params):
    return {i["title"] for i in client.get(URL, headers=who, params=params).json()["items"]}


def test_the_queue_shows_only_what_this_manager_can_decide(client, scene):
    assert titles(client, M1) == {"Standing desks"}  # not own request, not already approved by me, not delegated to someone else
    assert titles(client, M2) == {"Standing desks", "Own laptop", "Server racks", "Chairs"}  # includes what was delegated to me
    assert titles(client, M3) == {"Standing desks", "Own laptop", "Server racks"}


def test_my_decisions_and_all_views(client, scene):
    assert titles(client, M1, view="mine") == {"Server racks", "Printer toner", "100% cotton towels"}
    assert titles(client, M2, view="mine") == {"Chairs"}
    assert len(titles(client, M3, view="all")) == 6


def test_filters_search_sort_and_paging(client, scene):
    get = lambda **p: client.get(URL, headers=M1, params={"view": "all", **p}).json()  # noqa: E731
    assert {i["title"] for i in get(status="approved")["items"]} == {"Printer toner"} and get(status="rejected")["total"] == 1
    assert [i["title"] for i in get(priority="urgent")["items"]] == ["Server racks"]
    assert [i["title"] for i in get(q="SERVER")["items"]] == ["Server racks"] and get(q="pr-2026-000004")["total"] == 1 and get(q="alice")["total"] >= 5
    assert get(q="%")["total"] == 1 and get(q="_")["total"] == 0  # wildcards are literal
    assert get(sort="total_amount", order="desc")["items"][0]["title"] == "Server racks"
    p1, p2 = get(page_size=4, page=1), get(page_size=4, page=2)
    assert len(p1["items"]) == 4 and len(p2["items"]) == 2 and p1["total"] == 6 and not {i["id"] for i in p1["items"]} & {i["id"] for i in p2["items"]}
    for bad in ({"sort": "requester_id"}, {"view": "everything"}, {"status": "bogus"}, {"page_size": 101}, {"page": 0}):
        assert client.get(URL, headers=M1, params=bad).status_code == 422


def test_summaries_show_who_must_act(client, scene):
    rows = {i["title"]: i for i in client.get(URL, headers=M1, params={"view": "all"}).json()["items"]}
    assert rows["Chairs"]["waiting_for"] == "Max Manager" and rows["Standing desks"]["waiting_for"] == "Any manager" and rows["Printer toner"]["waiting_for"] is None
    assert rows["Server racks"]["current_level"] == 2 and rows["Server racks"]["total_levels"] == 2


def test_sql_injection_strings_are_inert(client, scene):
    assert client.get(URL, headers=M1, params={"q": "' OR 1=1 --", "view": "all"}).json()["total"] == 0
    assert client.get(f"{URL}/' OR '1'='1", headers=M1).status_code == 404


def test_dashboard_summary(client, scene, db):
    s1 = client.get(f"{URL}/summary", headers=M1).json()
    assert s1["waiting_for_me"] == 1 and s1["delegated_to_me"] == 0 and s1["overdue_for_me"] == 0
    assert s1["decided_by_me_30d"] == 3 and s1["approved_30d"] == 1 and s1["rejected_30d"] == 1  # A3 level 1, A5, A6 (delegating is not a decision)
    assert s1["approved_value_30d"] == {"USD": "1000.00"}
    assert s1["avg_decision_hours_30d"] is not None and len(s1["monthly"]) == 6 and s1["monthly"][-1]["count"] == 2
    s2 = client.get(f"{URL}/summary", headers=M2).json()
    assert s2["waiting_for_me"] == 4 and s2["delegated_to_me"] == 1 and s2["decided_by_me_30d"] == 0


def test_the_summary_counts_overdue_items_and_ignores_old_decisions(client, scene, db):
    for s in db.get(Approval, scene["A1"]).steps:
        s.escalated_at = utcnow()
    old = db.get(Approval, scene["A5"])
    old.decided_at = utcnow() - timedelta(days=45)
    db.commit()
    s = client.get(f"{URL}/summary", headers=M1).json()
    assert s["overdue_for_me"] == 1 and s["approved_30d"] == 0 and s["approved_value_30d"] == {}


# ---- service basics ------------------------------------------------------------------------------------
def test_health_openapi_and_request_ids(client):
    assert client.get("/health/live").json() == {"status": "ok"} and client.get("/health/ready").json() == {"status": "ok"}
    assert client.get("/health/live", headers={"X-Request-ID": "trace-9"}).headers["x-request-id"] == "trace-9"
    paths = client.get("/openapi.json").json()["paths"]
    assert "/api/v1/approvals" in paths and not any(p.startswith("/internal") for p in paths)


def test_readiness_fails_when_the_database_is_down(settings):
    from fastapi.testclient import TestClient

    from app.main import create_app
    assert TestClient(create_app(settings, create_engine("sqlite:////nonexistent-dir/x.db"))).get("/health/ready").status_code == 503


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
    assert {"approvals", "approval_steps", "approval_history", "approval_events"} <= set(inspect(eng).get_table_names())
    with eng.connect() as conn:
        assert compare_metadata(MigrationContext.configure(conn), Base.metadata) == []
    command.downgrade(cfg, "base")
    assert set(inspect(eng).get_table_names()) == {"alembic_version"}


def test_migration_generates_valid_mysql_ddl_offline(monkeypatch):
    cfg = _cfg("mysql+pymysql://u:p@localhost/approval_db", monkeypatch)
    buf = io.StringIO()
    cfg.output_buffer = buf
    command.upgrade(cfg, "head", sql=True)
    sql = buf.getvalue()
    for needle in ("CREATE TABLE approvals", "total_amount NUMERIC(14, 2) NOT NULL", "UNIQUE (request_id)", "ON DELETE CASCADE", "CREATE TABLE approval_events"):
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
def test_two_managers_deciding_the_same_step_at_once_produce_exactly_one_decision(app, register):
    aid = register()
    results, barrier = [], threading.Barrier(2)

    def decide(sub):
        user = TokenClaims(sub=sub, role="manager", name=sub, email=f"{sub}@example.com")
        with app.state.session_factory() as s:
            barrier.wait()
            try:
                service.approve(s, user, aid, None)
                results.append("ok")
            except HTTPException as e:
                results.append(e.status_code)

    threads = [threading.Thread(target=decide, args=(who,)) for who in ("mgr-1", "mgr-2")]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert sorted(results, key=str) == [409, "ok"]


@MYSQL
def test_concurrent_registration_of_the_same_request_creates_one_workflow(app, db):
    from procurehub_common.contracts.approval import ApprovalRegistration
    reg = ApprovalRegistration(**registration())
    ids, barrier = [], threading.Barrier(6)

    def go():
        with app.state.session_factory() as s:
            barrier.wait()
            ids.append(service.register(s, reg, app.state.settings.approval_thresholds).id)

    threads = [threading.Thread(target=go) for _ in range(6)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert len(set(ids)) == 1 and len(db.query(Approval).all()) == 1
    assert datetime.now() and svc()
