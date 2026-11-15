import json
from datetime import timedelta

import pytest

from app.models import QuotationEvent, Rfq
from tests.conftest import ADMIN, EMP, PROC, RFQ, rfq_body


def iso(dt):
    return dt.isoformat() + "Z"


def test_an_rfq_is_created_as_a_draft_from_an_approved_request(make_rfq, world):
    rfq = make_rfq()
    assert rfq["status"] == "draft" and rfq["number"].startswith("RFQ-") and rfq["purchase_request_number"] == "PR-2026-000001"
    assert rfq["title"] == "Laptops for the design team" and rfq["department"] == "Design" and rfq["currency"] == "INR"
    assert [(i["line_no"], i["quantity"], i["unit"], i["estimated_unit_price"]) for i in rfq["items"]] == [(1, "4.000", "each", "24000.00"), (2, "4.000", "each", "750.50")]
    assert rfq["budget_amount"] == "99002.00" and rfq["version"] == 1 and rfq["invitations"] == [] and rfq["actions"] == ["edit", "invite", "publish", "cancel"]
    assert rfq["history"][0]["action"] == "created" and rfq["history"][0]["actor_name"] == "Pat Procurement"
    assert ("pr", "GET", "/internal/v1/purchase-requests/pr-1") in world.calls


def test_title_and_item_clarifications_are_applied_but_quantities_cannot_be_changed(make_rfq):
    rfq = make_rfq(title="  Design laptops  ", items=[{"line_no": 1, "description": "14-inch laptop, aluminium", "specification": "16 GB memory, 512 GB disk"}],
                   **{"quantity": "1"})
    assert rfq["title"] == "Design laptops"
    assert rfq["items"][0]["description"] == "14-inch laptop, aluminium" and rfq["items"][0]["specification"] == "16 GB memory, 512 GB disk"
    assert rfq["items"][0]["quantity"] == "4.000" and rfq["items"][1]["description"] == "Laptop sleeve"


@pytest.mark.parametrize("status", ["draft", "submitted", "rejected", "cancelled"])
def test_only_approved_requests_can_go_out_for_quotation(client, world, clock, status):
    world.add_request("pr-2", "PR-2026-000002", status=status)
    r = client.post(RFQ, headers=PROC, json=rfq_body(clock, purchase_request_id="pr-2"))
    assert r.status_code == 422 and "Only approved" in r.json()["detail"] and status in r.json()["detail"]


def test_unknown_request_and_empty_request_are_refused(client, world, clock):
    assert client.post(RFQ, headers=PROC, json=rfq_body(clock, purchase_request_id="nope")).status_code == 422
    world.requests["pr-1"]["items"] = []
    assert client.post(RFQ, headers=PROC, json=rfq_body(clock)).status_code == 422


def test_a_request_can_have_only_one_live_rfq_and_cancelling_frees_it(client, make_rfq, clock):
    first = make_rfq()
    again = client.post(RFQ, headers=PROC, json=rfq_body(clock))
    assert again.status_code == 409 and first["number"] in again.json()["detail"]
    assert client.post(f"{RFQ}/{first['id']}/cancel", headers=PROC, json={"reason": "Scope changed"}).status_code == 200
    second = make_rfq()
    assert second["id"] != first["id"] and second["number"] != first["number"]


def test_two_requests_racing_past_the_check_are_stopped_by_the_unique_index(client, make_rfq, clock, monkeypatch):
    """Both requests pass the "already has an RFQ" check when they run at the same instant; the database must still refuse the second."""
    from app import service
    make_rfq()
    monkeypatch.setattr(service, "live_rfq_for", lambda db, request_id: None)
    r = client.post(RFQ, headers=PROC, json=rfq_body(clock))
    assert r.status_code == 409 and r.json()["detail"] == "This purchase request already has an RFQ in progress."  # the index's message, not the check's
    assert client.get(RFQ, headers=PROC).json()["total"] == 1


@pytest.mark.parametrize("delta,ok", [(timedelta(minutes=30), False), (timedelta(hours=-1), False), (timedelta(days=400), False), (timedelta(hours=2), True), (timedelta(days=30), True)])
def test_the_deadline_must_be_a_sensible_time_ahead(client, clock, delta, ok):
    r = client.post(RFQ, headers=PROC, json=rfq_body(clock, deadline=iso(clock.now + delta)))
    assert (r.status_code == 201) is ok, r.text
    if not ok:
        assert r.status_code == 422 and "deadline" in r.json()["detail"].lower()


def test_deadlines_with_a_time_zone_are_converted_to_utc(client, clock):
    local = (clock.now + timedelta(hours=48)).isoformat() + "+05:30"  # 5.5 hours earlier in UTC
    r = client.post(RFQ, headers=PROC, json=rfq_body(clock, deadline=local))
    assert r.status_code == 201
    assert r.json()["deadline"] == iso(clock.now + timedelta(hours=48) - timedelta(hours=5, minutes=30))


@pytest.mark.parametrize("field,value", [("title", "ab"), ("title", "x" * 151), ("description", "x" * 4001), ("deadline", "not a date"), ("purchase_request_id", ""),
                                         ("items", [{"line_no": 9, "description": "Ghost"}]), ("items", [{"line_no": 1, "description": " "}]),
                                         ("items", [{"line_no": 1, "description": "a"}, {"line_no": 1, "description": "b"}])])
def test_invalid_rfq_fields_are_rejected(client, clock, field, value):
    assert client.post(RFQ, headers=PROC, json=rfq_body(clock, **{field: value})).status_code == 422


def test_a_draft_can_be_edited_with_the_version_it_was_loaded_at(client, make_rfq, clock):
    rfq = make_rfq()
    body = {"version": 1, "title": "Revised title", "description": "New", "requirements": "New reqs", "deadline": iso(clock.now + timedelta(days=5)),
            "items": [{"line_no": 2, "description": "Laptop sleeve, padded", "specification": "Fits 14 inch"}]}
    r = client.put(f"{RFQ}/{rfq['id']}", headers=PROC, json=body)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["title"] == "Revised title" and out["version"] == 2 and out["items"][1]["specification"] == "Fits 14 inch" and out["items"][0]["description"] == "14-inch laptop"
    assert out["history"][-1]["action"] == "updated"
    stale = client.put(f"{RFQ}/{rfq['id']}", headers=PROC, json=body)
    assert stale.status_code == 409 and "changed somewhere else" in stale.json()["detail"]


def test_an_issued_rfq_cannot_be_edited(client, issued, clock):
    rfq = issued()
    body = {"version": rfq["version"], "title": "Sneaky change", "deadline": iso(clock.now + timedelta(days=5))}
    r = client.put(f"{RFQ}/{rfq['id']}", headers=PROC, json=body)
    assert r.status_code == 409 and "draft" in r.json()["detail"]
    assert client.get(f"{RFQ}/{rfq['id']}", headers=PROC).json()["title"] == rfq["title"]


def test_publishing_needs_an_invited_vendor_and_a_future_deadline(client, make_rfq, clock):
    rfq = make_rfq()
    r = client.post(f"{RFQ}/{rfq['id']}/publish", headers=PROC)
    assert r.status_code == 422 and "Invite at least one vendor." in r.json()["detail"]
    client.post(f"{RFQ}/{rfq['id']}/invitations", headers=PROC, json={"vendor_ids": ["v-a"]})
    clock.advance(hours=47, minutes=30)  # the draft's deadline is now too close
    r = client.post(f"{RFQ}/{rfq['id']}/publish", headers=PROC)
    assert r.status_code == 422 and any("deadline" in p for p in r.json()["detail"])


def test_publishing_sends_the_invitations_and_issues_the_rfq(issued, client):
    rfq = issued()
    assert rfq["status"] == "issued" and rfq["issued_at"] and all(i["sent_at"] for i in rfq["invitations"]) and len(rfq["invitations"]) == 3
    assert rfq["history"][-1]["action"] == "issued" and rfq["version"] == 2
    assert "close" in rfq["actions"] and "edit" not in rfq["actions"] and "publish" not in rfq["actions"]
    assert client.post(f"{RFQ}/{rfq['id']}/publish", headers=PROC).status_code == 409  # not twice


def test_publishing_refuses_a_vendor_that_was_suspended_after_being_invited(client, make_rfq, world):
    rfq = make_rfq()
    client.post(f"{RFQ}/{rfq['id']}/invitations", headers=PROC, json={"vendor_ids": ["v-a", "v-b"]})
    world.vendors["v-b"]["status"] = "suspended"
    r = client.post(f"{RFQ}/{rfq['id']}/publish", headers=PROC)
    assert r.status_code == 409 and "Bravo Traders" in r.json()["detail"] and "Acme" not in r.json()["detail"]
    assert client.get(f"{RFQ}/{rfq['id']}", headers=PROC).json()["status"] == "draft"


def test_a_draft_cannot_be_closed(client, make_rfq):
    draft = make_rfq()
    assert client.post(f"{RFQ}/{draft['id']}/close", headers=PROC).status_code == 409


def test_an_issued_rfq_can_be_closed_early_and_then_not_again(client, issued):
    rfq = issued()
    r = client.post(f"{RFQ}/{rfq['id']}/close", headers=PROC)
    assert r.status_code == 200 and r.json()["status"] == "closed" and r.json()["closed_at"] and r.json()["quotations_open"] is True
    assert client.post(f"{RFQ}/{rfq['id']}/close", headers=PROC).status_code == 409


@pytest.mark.parametrize("path,body", [("publish", None), ("close", None), ("cancel", {"reason": "abc"}), ("extend", {"version": 1, "deadline": "2099-01-01T00:00:00Z"}),
                                       ("invitations", {"vendor_ids": ["v-a"]})])
def test_a_cancelled_rfq_accepts_no_further_changes(client, make_rfq, path, body):
    rfq = make_rfq()
    assert client.post(f"{RFQ}/{rfq['id']}/cancel", headers=PROC, json={"reason": "Not needed"}).status_code == 200
    r = client.post(f"{RFQ}/{rfq['id']}/{path}", headers=PROC, **({"json": body} if body else {}))
    assert r.status_code == 409, (path, r.text)
    out = client.get(f"{RFQ}/{rfq['id']}", headers=PROC).json()
    assert out["status"] == "cancelled" and out["cancel_reason"] == "Not needed" and out["actions"] == []


def test_cancel_needs_a_reason(client, make_rfq):
    rfq = make_rfq()
    assert client.post(f"{RFQ}/{rfq['id']}/cancel", headers=PROC, json={}).status_code == 422
    assert client.post(f"{RFQ}/{rfq['id']}/cancel", headers=PROC, json={"reason": "  "}).status_code == 422
    assert client.post(f"{RFQ}/{rfq['id']}/cancel", headers=PROC, json={"reason": "Budget cut"}).status_code == 200
    assert client.post(f"{RFQ}/{rfq['id']}/cancel", headers=PROC, json={"reason": "Again"}).status_code == 409


def test_the_deadline_can_be_extended_but_never_shortened_or_after_it_passed(client, issued, clock):
    rfq = issued()
    later = iso(clock.now + timedelta(days=7))
    r = client.post(f"{RFQ}/{rfq['id']}/extend", headers=PROC, json={"version": rfq["version"], "deadline": later})
    assert r.status_code == 200 and r.json()["deadline"] == later and r.json()["history"][-1]["action"] == "deadline_extended"
    version = r.json()["version"]
    assert client.post(f"{RFQ}/{rfq['id']}/extend", headers=PROC, json={"version": version, "deadline": iso(clock.now + timedelta(days=3))}).status_code == 422  # earlier
    assert client.post(f"{RFQ}/{rfq['id']}/extend", headers=PROC, json={"version": version - 1, "deadline": iso(clock.now + timedelta(days=8))}).status_code == 409  # stale
    clock.advance(days=8)
    r = client.post(f"{RFQ}/{rfq['id']}/extend", headers=PROC, json={"version": version, "deadline": iso(clock.now + timedelta(days=3))})
    assert r.status_code == 409 and "has passed" in r.json()["detail"]


def test_the_history_records_every_step_in_order(client, issued):
    rfq = issued()
    client.post(f"{RFQ}/{rfq['id']}/close", headers=PROC)
    out = client.get(f"{RFQ}/{rfq['id']}", headers=PROC).json()
    assert [h["action"] for h in out["history"]] == ["created", "vendors_invited", "issued", "closed"]
    assert [h["seq"] for h in out["history"]] == [1, 2, 3, 4] and out["history"][-1]["to_status"] == "closed"


def test_every_change_writes_an_outbox_event_for_later_notification(client, issued, db):
    rfq = issued()
    types = sorted(e.type for e in db.query(QuotationEvent).filter_by(rfq_id=rfq["id"]))
    assert types == ["rfq_created", "rfq_issued", "vendors_invited"]
    issued_event = next(e for e in db.query(QuotationEvent) if e.type == "rfq_issued")
    assert sorted(json.loads(issued_event.payload)["vendor_ids"]) == ["v-a", "v-b", "v-c"] and issued_event.published_at is None


def test_a_failed_creation_leaves_nothing_behind(client, clock, db):
    client.post(RFQ, headers=PROC, json=rfq_body(clock, items=[{"line_no": 9, "description": "Ghost"}]))
    assert db.query(Rfq).count() == 0 and db.query(QuotationEvent).count() == 0


def test_eligible_requests_are_the_approved_ones_marked_with_any_live_rfq(client, make_rfq, world):
    world.add_request("pr-2", "PR-2026-000002")
    world.add_request("pr-3", "PR-2026-000003", status="submitted")
    rfq = make_rfq()
    out = client.get(f"{RFQ}/eligible-requests", headers=PROC).json()
    assert out["total"] == 2 and {i["number"] for i in out["items"]} == {"PR-2026-000001", "PR-2026-000002"}
    by_number = {i["number"]: i for i in out["items"]}
    assert by_number["PR-2026-000001"]["rfq_id"] == rfq["id"] and by_number["PR-2026-000001"]["rfq_number"] == rfq["number"] and by_number["PR-2026-000002"]["rfq_id"] is None
    assert by_number["PR-2026-000002"]["item_count"] == 2 and by_number["PR-2026-000002"]["total_amount"] == "99002.00"
    assert client.get(f"{RFQ}/eligible-requests?q=000002", headers=PROC).json()["total"] == 1
    assert client.get(f"{RFQ}/eligible-requests?page_size=51", headers=PROC).status_code == 422


def test_listing_filters_searches_sorts_and_pages(client, make_rfq, world, issued):
    a = make_rfq(title="Alpha laptops")
    world.add_request("pr-2", "PR-2026-000002")
    b = make_rfq(purchase_request_id="pr-2", title="100% Bravo_chairs")
    client.post(f"{RFQ}/{b['id']}/cancel", headers=PROC, json={"reason": "No longer needed"})
    out = client.get(RFQ, headers=PROC).json()
    assert out["total"] == 2 and {i["title"] for i in out["items"]} == {"100% Bravo_chairs", "Alpha laptops"}  # (same-second creations have no fixed order; sorting is tested below)
    assert [i["id"] for i in client.get(f"{RFQ}?status=draft", headers=PROC).json()["items"]] == [a["id"]]
    assert [i["id"] for i in client.get(f"{RFQ}?q=alpha", headers=PROC).json()["items"]] == [a["id"]]
    assert client.get(f"{RFQ}?q=%25", headers=PROC).json()["total"] == 1 and client.get(f"{RFQ}?q=_", headers=PROC).json()["total"] == 1
    assert client.get(f"{RFQ}?q={a['number']}", headers=PROC).json()["total"] == 1
    assert client.get(f"{RFQ}?sort=title&order=asc&page_size=1&page=2", headers=PROC).json()["items"][0]["title"] == "Alpha laptops"
    assert client.get(f"{RFQ}?sort=title&order=desc", headers=PROC).json()["items"][0]["title"] == "Alpha laptops"
    for bad in ("status=bogus", "page=0", "page_size=101", "sort=budget_amount", "order=up"):
        assert client.get(f"{RFQ}?{bad}", headers=PROC).status_code == 422, bad


def test_summary_counts_by_status_and_what_awaits_comparison(client, make_rfq, issued, world, clock):
    assert client.get(f"{RFQ}/summary", headers=PROC).json() == {"counts": {"draft": 0, "issued": 0, "closed": 0, "awarded": 0, "cancelled": 0}, "awaiting_comparison": 0}
    issued()
    world.add_request("pr-2", "PR-2026-000002")
    make_rfq(purchase_request_id="pr-2")
    s = client.get(f"{RFQ}/summary", headers=PROC).json()
    assert s["counts"]["issued"] == 1 and s["counts"]["draft"] == 1 and s["awaiting_comparison"] == 0
    clock.advance(days=3)
    assert client.get(f"{RFQ}/summary", headers=PROC).json()["awaiting_comparison"] == 1


def test_services_being_down_or_missing_gives_a_503_never_a_guess(client, clock, world, make_rfq):
    world.pr_down = True
    assert client.post(RFQ, headers=PROC, json=rfq_body(clock)).status_code == 503
    assert client.get(f"{RFQ}/eligible-requests", headers=PROC).status_code == 503
    world.pr_down = False
    rfq = make_rfq()
    world.vendor_down = True
    assert client.post(f"{RFQ}/{rfq['id']}/invitations", headers=PROC, json={"vendor_ids": ["v-a"]}).status_code == 503
    assert client.get(f"{RFQ}/{rfq['id']}", headers=PROC).status_code == 200  # reading our own data needs no other service


def test_a_service_that_is_not_configured_says_so(engine, clock):
    from fastapi.testclient import TestClient

    from app.config import Settings
    from app.main import create_app
    from tests.conftest import INTERNAL, SECRET
    bare = TestClient(create_app(Settings(database_url="sqlite://", jwt_secret=SECRET, internal_jwt_secret=INTERNAL, log_level="CRITICAL"), engine))
    r = bare.get(f"{RFQ}/eligible-requests", headers=PROC)
    assert r.status_code == 503 and "not configured" in r.json()["detail"]


def test_unknown_rfq_is_404(client):
    for h in (PROC,):
        assert client.get(f"{RFQ}/nope", headers=h).status_code == 404
        assert client.post(f"{RFQ}/nope/publish", headers=h).status_code == 404


def test_roles_without_rfq_permissions_cannot_create(client, clock):
    for h in (ADMIN, EMP):
        assert client.post(RFQ, headers=h, json=rfq_body(clock)).status_code == 403
