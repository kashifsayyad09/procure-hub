from datetime import date, timedelta

import pytest

from app.models import Quotation, QuotationEvent
from tests.conftest import PROC, QUO, RFQ, VA, VB, VC, VNONE, VX


def body(rfq, prices=("23000.00", "700.00"), **over):
    base = {"rfq_id": rfq["id"], "currency": "INR", "lead_time_days": 14, "valid_until": (date.today() + timedelta(days=60)).isoformat(), "payment_terms_days": 30,
            "terms": "Delivery included.", "items": [{"rfq_item_id": it["id"], "unit_price": p} for it, p in zip(rfq["items"], prices, strict=False) if p is not None]}
    base.update(over)
    return base


def test_a_draft_has_a_line_for_every_rfq_item_and_a_server_computed_total(client, issued):
    rfq = issued()
    r = client.post(QUO, headers=VA, json=body(rfq, ("23000.00", None)))
    assert r.status_code == 201, r.text
    q = r.json()
    assert q["status"] == "draft" and q["number"].startswith("QTN-") and q["vendor_name"] == "Acme Supplies" and q["version"] == 1
    assert [(i["line_no"], i["quantity"], i["unit_price"], i["line_total"]) for i in q["items"]] == [(1, "4.000", "23000.0000", "92000.00"), (2, "4.000", None, None)]
    assert q["total_amount"] == "92000.00" and q["complete"] is False and q["missing_items"] == [2] and q["can_edit"] is True and q["can_submit"] is True


def test_money_is_exact_with_no_floating_point_drift(client, issued):
    rfq = issued()
    q = client.post(QUO, headers=VA, json=body(rfq, ("0.1", "0.2"))).json()
    assert [i["line_total"] for i in q["items"]] == ["0.40", "0.80"] and q["total_amount"] == "1.20"  # 4 x 0.1 + 4 x 0.2, never 1.2000000000000002
    third = client.post(QUO, headers=VB, json=body(rfq, ("33.3333", "0.0005"))).json()
    assert [i["line_total"] for i in third["items"]] == ["133.33", "0.00"] and third["total_amount"] == "133.33"  # 4 x 33.3333 = 133.3332; 4 x 0.0005 = 0.002
    half = client.post(QUO, headers=VC, json=body(rfq, ("0.125", "0.125"))).json()
    assert [i["line_total"] for i in half["items"]] == ["0.50", "0.50"]  # 0.5 exactly
    assert client.post(QUO, headers=VA, json=body(rfq)).status_code == 409  # A already has the first one above


def test_rounding_goes_half_up_to_the_cent(client, issued, world):
    world.requests["pr-1"]["items"] = world.requests["pr-1"]["items"][:1]
    world.requests["pr-1"]["items"][0].update(quantity="3.000", unit_price="1.00", line_total="3.00")
    world.requests["pr-1"]["total_amount"] = "3.00"
    rfq = issued()
    q = client.post(QUO, headers=VA, json=body(rfq, ("0.835",))).json()
    assert q["items"][0]["line_total"] == "2.51" and q["total_amount"] == "2.51"  # 3 x 0.835 = 2.505, half up


def test_quantities_come_from_the_rfq_and_cannot_be_changed_by_the_vendor(client, issued):
    rfq = issued()
    payload = body(rfq)
    payload["items"][0]["quantity"] = "1"
    payload["items"][0]["line_total"] = "1.00"
    q = client.post(QUO, headers=VA, json=payload).json()
    assert q["items"][0]["quantity"] == "4.000" and q["items"][0]["line_total"] == "92000.00"


def test_the_vendor_cannot_set_status_total_vendor_or_number(client, issued, db):
    rfq = issued()
    r = client.post(QUO, headers=VA, json=body(rfq, status="selected", total_amount="1.00", vendor_id="v-b", vendor_name="Evil", number="QTN-1", version=99, revision=7))
    assert r.status_code == 201
    q = r.json()
    assert q["status"] == "draft" and q["total_amount"] == "94800.00" and q["vendor_id"] == "v-a" and q["vendor_name"] == "Acme Supplies" and q["number"] != "QTN-1"
    assert q["version"] == 1 and q["revision"] == 1
    assert db.query(Quotation).one().vendor_id == "v-a"


@pytest.mark.parametrize("change", [
    {"items": [{"rfq_item_id": "x", "unit_price": "-1"}]}, {"currency": "JPY"}, {"currency": "inr"}, {"lead_time_days": 0}, {"lead_time_days": 731}, {"payment_terms_days": -1},
    {"payment_terms_days": 366}, {"terms": "x" * 4001}, {"valid_until": "not-a-date"}, {"items": [{"rfq_item_id": "x", "unit_price": "1.00001"}]},
    {"items": [{"rfq_item_id": "x", "unit_price": "NaN"}]}, {"items": [{"rfq_item_id": "x", "unit_price": "1e30"}]}, {"items": [{"rfq_item_id": "x", "unit_price": "abc"}]},
])
def test_invalid_quotation_fields_are_rejected(client, issued, change):
    rfq = issued()
    if "items" in change:
        change = {"items": [{**i, "rfq_item_id": rfq["items"][0]["id"]} for i in change["items"]]}
    assert client.post(QUO, headers=VA, json=body(rfq, **change)).status_code == 422, change


def test_lines_must_belong_to_the_rfq_and_appear_once(client, issued):
    rfq = issued()
    dup = body(rfq)
    dup["items"].append(dup["items"][0])
    assert client.post(QUO, headers=VA, json=dup).status_code == 422
    foreign = body(rfq)
    foreign["items"][0]["rfq_item_id"] = "someone-elses-line"
    r = client.post(QUO, headers=VA, json=foreign)
    assert r.status_code == 422 and "not on the RFQ" in r.json()["detail"]


def test_a_free_item_with_a_zero_price_is_allowed(client, issued):
    rfq = issued()
    q = client.post(QUO, headers=VA, json=body(rfq, ("0", "0"))).json()
    assert q["total_amount"] == "0.00" and q["complete"] is True


def test_the_quotation_must_stay_valid_until_the_rfq_deadline(client, issued, clock):
    rfq = issued()
    deadline_day = (clock.now + timedelta(hours=48)).date()
    too_early = deadline_day - timedelta(days=1)
    assert client.post(QUO, headers=VA, json=body(rfq, valid_until=too_early.isoformat())).status_code == 422
    assert client.post(QUO, headers=VA, json=body(rfq, valid_until=(date.today() + timedelta(days=800)).isoformat())).status_code == 422
    assert client.post(QUO, headers=VA, json=body(rfq, valid_until=max(deadline_day, date.today()).isoformat())).status_code == 201


def test_a_draft_can_be_edited_with_its_version(client, issued):
    rfq = issued()
    q = client.post(QUO, headers=VA, json=body(rfq, ("1.00", None))).json()
    r = client.put(f"{QUO}/{q['id']}", headers=VA, json=body(rfq, ("2.50", "3.00"), version=1, lead_time_days=7))
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["total_amount"] == "22.00" and out["lead_time_days"] == 7 and out["version"] == 2 and out["complete"] is True
    stale = client.put(f"{QUO}/{q['id']}", headers=VA, json=body(rfq, version=1))
    assert stale.status_code == 409 and "changed somewhere else" in stale.json()["detail"]
    assert client.put(f"{QUO}/{q['id']}", headers=VA, json=body(rfq)).status_code == 422  # version is required


def test_submitting_needs_a_lead_time_a_validity_and_a_price(client, issued):
    rfq = issued()
    q = client.post(QUO, headers=VA, json={"rfq_id": rfq["id"], "currency": "INR"}).json()
    assert q["can_submit"] is False and len(q["problems"]) == 3
    r = client.post(f"{QUO}/{q['id']}/submit", headers=VA)
    assert r.status_code == 422
    assert set(r.json()["detail"]) == {"Enter the delivery lead time in days.", "Enter how long the quotation is valid.", "Price at least one item."}
    assert client.get(f"{QUO}/{q['id']}", headers=VA).json()["status"] == "draft"


def test_a_quotation_is_submitted_once_and_keeps_its_details(client, quote, issued, db):
    rfq = issued()
    q = quote(VA, rfq)
    assert q["status"] == "submitted" and q["submitted_at"]
    assert q["total_amount"] == "94800.00" and q["lead_time_days"] == 14 and q["terms"] == "Delivery included." and q["can_edit"] is False and q["can_withdraw"] is True
    again = client.post(f"{QUO}/{q['id']}/submit", headers=VA)
    assert again.status_code == 409 and "already submitted" in again.json()["detail"]
    assert client.put(f"{QUO}/{q['id']}", headers=VA, json=body(rfq, version=q["version"])).status_code == 409
    dup = client.post(QUO, headers=VA, json=body(rfq))
    assert dup.status_code == 409 and "already have a quotation" in dup.json()["detail"]
    assert db.query(Quotation).count() == 1
    assert db.query(QuotationEvent).filter_by(type="quotation_submitted").count() == 1  # Phase 10: notify procurement


def test_a_second_create_racing_the_first_is_stopped_by_the_unique_index(client, issued, monkeypatch):
    from app import service
    rfq = issued()
    assert client.post(QUO, headers=VA, json=body(rfq)).status_code == 201
    real = service.create_quotation

    class Blind:
        def __init__(self, db):
            self.db = db

        def scalar(self, stmt, *a, **k):
            return None if "SELECT quotations.id" in str(stmt) else self.db.scalar(stmt, *a, **k)

        def __getattr__(self, name):
            return getattr(self.db, name)
    monkeypatch.setattr(service, "create_quotation", lambda db, *a, **k: real(Blind(db), *a, **k))
    r = client.post(QUO, headers=VA, json=body(rfq))
    assert r.status_code == 409 and "already have a quotation" in r.json()["detail"]


def test_submission_is_refused_after_the_deadline_and_nothing_changes(client, issued, clock):
    rfq = issued()
    q = client.post(QUO, headers=VA, json=body(rfq)).json()
    clock.advance(days=3)
    r = client.post(f"{QUO}/{q['id']}/submit", headers=VA)
    assert r.status_code == 409 and "deadline has passed" in r.json()["detail"]
    assert client.put(f"{QUO}/{q['id']}", headers=VA, json=body(rfq, version=1)).status_code == 409
    assert client.post(QUO, headers=VB, json=body(rfq)).status_code == 409
    assert client.get(f"{QUO}/{q['id']}", headers=VA).json()["status"] == "draft"


def test_submission_is_refused_once_the_rfq_is_closed(client, issued):
    rfq = issued()
    q = client.post(QUO, headers=VA, json=body(rfq)).json()
    client.post(f"{RFQ}/{rfq['id']}/close", headers=PROC)
    r = client.post(f"{QUO}/{q['id']}/submit", headers=VA)
    assert r.status_code == 409 and "no longer taking quotations" in r.json()["detail"]


def test_a_cancelled_rfq_takes_no_quotations(client, issued):
    rfq = issued()
    q = client.post(QUO, headers=VA, json=body(rfq)).json()
    client.post(f"{RFQ}/{rfq['id']}/cancel", headers=PROC, json={"reason": "Not needed"})
    r = client.post(f"{QUO}/{q['id']}/submit", headers=VA)
    assert r.status_code == 409 and "cancelled" in r.json()["detail"]


def test_a_submitted_quotation_can_be_withdrawn_for_changes_before_the_deadline(client, issued, quote):
    rfq = issued()
    q = quote(VA, rfq)
    w = client.post(f"{QUO}/{q['id']}/withdraw", headers=VA)
    assert w.status_code == 200 and w.json()["status"] == "draft" and w.json()["revision"] == 2 and w.json()["submitted_at"] is None
    assert client.post(f"{QUO}/{q['id']}/withdraw", headers=VA).status_code == 409
    edited = client.put(f"{QUO}/{q['id']}", headers=VA, json=body(rfq, ("22000.00", "650.00"), version=w.json()["version"]))
    assert edited.status_code == 200
    again = client.post(f"{QUO}/{q['id']}/submit", headers=VA)
    assert again.status_code == 200 and again.json()["status"] == "submitted" and again.json()["total_amount"] == "90600.00"


def test_withdrawing_is_refused_after_the_deadline(client, issued, quote, clock):
    rfq = issued()
    q = quote(VA, rfq)
    clock.advance(days=3)
    assert client.post(f"{QUO}/{q['id']}/withdraw", headers=VA).status_code == 409


def test_a_vendor_can_only_touch_their_own_quotation(client, issued, quote):
    rfq = issued()
    q = quote(VA, rfq, submit=False)
    for call in (lambda: client.get(f"{QUO}/{q['id']}", headers=VB), lambda: client.put(f"{QUO}/{q['id']}", headers=VB, json=body(rfq, version=1)),
                 lambda: client.post(f"{QUO}/{q['id']}/submit", headers=VB), lambda: client.post(f"{QUO}/{q['id']}/withdraw", headers=VB)):
        assert call().status_code == 404
    assert client.get(f"{QUO}/{q['id']}", headers=VA).status_code == 200
    assert client.get(f"{QUO}/mine", headers=VB).json()["total"] == 0


def test_a_vendor_cannot_quote_on_an_rfq_they_were_not_invited_to(client, issued):
    rfq = issued(vendors=("v-a",))
    assert client.post(QUO, headers=VB, json=body(rfq)).status_code == 404
    assert client.post(QUO, headers=VB, json=body({"id": "nope", "items": []})).status_code == 404


def test_a_vendor_without_a_profile_or_unverified_cannot_quote(client, issued, world):
    rfq = issued()
    assert client.post(QUO, headers=VNONE, json=body(rfq)).status_code == 403
    q = client.post(QUO, headers=VA, json=body(rfq)).json()
    world.vendors["v-a"]["status"] = "suspended"  # suspended after being invited
    r = client.post(f"{QUO}/{q['id']}/submit", headers=VA)
    assert r.status_code == 403 and "not verified" in r.json()["detail"]
    assert client.post(QUO, headers=VX, json=body(rfq)).status_code in (403, 404)


def test_my_quotations_lists_only_mine_with_their_rfq(client, issued, quote):
    rfq = issued()
    quote(VA, rfq)
    quote(VB, rfq, submit=False)
    mine = client.get(f"{QUO}/mine", headers=VA).json()
    assert mine["total"] == 1 and mine["items"][0]["rfq_number"] == rfq["number"] and mine["items"][0]["status"] == "submitted" and mine["items"][0]["total_amount"] == "94800.00"
    assert client.get(f"{QUO}/mine?page_size=101", headers=VA).status_code == 422


def test_the_vendor_sees_their_draft_in_the_rfq_view(client, issued, quote):
    rfq = issued()
    q = quote(VA, rfq, submit=False)
    d = client.get(f"{RFQ}/invited/{rfq['id']}", headers=VA).json()
    assert d["quotation"]["id"] == q["id"] and d["quotation"]["status"] == "draft"


# ---- what procurement may see ----------------------------------------------------------------------
def test_prices_are_sealed_from_procurement_until_the_deadline_or_close(client, issued, quote, clock):
    rfq = issued()
    q = quote(VA, rfq)
    quote(VB, rfq, submit=False)
    sealed = client.get(f"{RFQ}/{rfq['id']}/quotations", headers=PROC).json()
    assert sealed["quotations_open"] is False
    by = {r["vendor_name"]: r for r in sealed["rows"]}
    assert by["Acme Supplies"]["status"] == "submitted" and by["Acme Supplies"]["total_amount"] is None and by["Acme Supplies"]["id"] is None
    assert by["Bravo Traders"]["status"] == "draft" and by["Cedar Co"]["status"] is None
    assert "94800" not in client.get(f"{RFQ}/{rfq['id']}/quotations", headers=PROC).text and "23000" not in client.get(f"{RFQ}/{rfq['id']}", headers=PROC).text.replace("24000", "")
    assert client.get(f"{QUO}/{q['id']}", headers=PROC).status_code == 409
    assert client.get(f"{RFQ}/{rfq['id']}/comparison", headers=PROC).status_code == 409
    clock.advance(days=3)
    opened = {r["vendor_name"]: r for r in client.get(f"{RFQ}/{rfq['id']}/quotations", headers=PROC).json()["rows"]}
    assert opened["Acme Supplies"]["total_amount"] == "94800.00" and opened["Acme Supplies"]["lead_time_days"] == 14
    assert opened["Bravo Traders"]["total_amount"] is None  # a draft is never shown
    assert client.get(f"{QUO}/{q['id']}", headers=PROC).json()["total_amount"] == "94800.00"


def test_closing_early_opens_the_prices(client, issued, quote):
    rfq = issued()
    q = quote(VA, rfq)
    assert client.get(f"{QUO}/{q['id']}", headers=PROC).status_code == 409
    client.post(f"{RFQ}/{rfq['id']}/close", headers=PROC)
    assert client.get(f"{QUO}/{q['id']}", headers=PROC).status_code == 200


def test_procurement_can_never_read_a_vendors_draft(client, issued, quote, clock):
    rfq = issued()
    d = quote(VA, rfq, submit=False)
    clock.advance(days=3)
    assert client.get(f"{QUO}/{d['id']}", headers=PROC).status_code == 404
    assert client.get(f"{RFQ}/{rfq['id']}/comparison", headers=PROC).json()["quotations"] == []
