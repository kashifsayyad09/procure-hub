import json
import os
import threading

import pytest

from app.models import QuotationEvent, Selection
from tests.conftest import PROC, PROC2, QUO, RFQ, VA, VB, VC, svc_header

CMP = "/comparison"


@pytest.fixture
def rfq_with_quotes(client, issued, quote):
    """Vendor A 94,800 in 14 days; B 90,600 in 21 days; C prices only the first item (96,000, 7 days)."""
    rfq = issued()
    qs = {"a": quote(VA, rfq, ("23000.00", "700.00"), lead=14), "b": quote(VB, rfq, ("22000.00", "650.00"), lead=21), "c": quote(VC, rfq, ("24000.00", None), lead=7)}
    return rfq, qs


@pytest.fixture
def opened(rfq_with_quotes, clock):
    clock.advance(days=3)
    return rfq_with_quotes


def comparison(client, rfq):
    r = client.get(f"{RFQ}/{rfq['id']}{CMP}", headers=PROC)
    assert r.status_code == 200, r.text
    return r.json()


def rows(cmp):
    return {r["vendor_name"]: r for r in cmp["quotations"]}


def evaluate(client, rfq, q, comp, terms, version=None, h=PROC):
    body = {"compliance_score": comp, "compliance_note": "Meets the specification." if comp is not None else None, "terms_score": terms,
            "terms_note": "Net 30, delivery included." if terms is not None else None}
    if version:
        body["version"] = version
    return client.put(f"{RFQ}/{rfq['id']}/evaluations/{q['id']}", headers=h, json=body)


# ---- comparison ------------------------------------------------------------------------------------
def test_the_comparison_shows_exact_totals_differences_and_missing_items(client, opened):
    rfq, qs = opened
    c = comparison(client, rfq)
    r = rows(c)
    assert len(r) == 3
    assert r["Acme Supplies"]["total_amount"] == "94800.00" and r["Bravo Traders"]["total_amount"] == "90600.00" and r["Cedar Co"]["total_amount"] == "96000.00"
    assert [(line["line_no"], line["unit_price"], line["line_total"]) for line in r["Bravo Traders"]["lines"]] == [(1, "22000.0000", "88000.00"), (2, "650.0000", "2600.00")]
    assert r["Cedar Co"]["complete"] is False and r["Cedar Co"]["missing_items"] == [2] and r["Acme Supplies"]["missing_items"] == []
    assert r["Bravo Traders"]["lowest_price"] is True and r["Acme Supplies"]["fastest"] is True and r["Cedar Co"]["lowest_price"] is False
    assert r["Acme Supplies"]["within_budget"] is True and r["Cedar Co"]["within_budget"] is None  # a partial quotation is not judged against the budget
    assert r["Acme Supplies"]["vendor_status"] == "verified" and c["vendor_info_available"] is True and c["mixed_currencies"] is False and c["note"] is None
    assert c["rfq"]["budget_amount"] == "99002.00" and c["weights"] == {"price": 40, "delivery": 20, "compliance": 25, "terms": 15}


def test_calculated_scores_and_missing_inputs_are_explicit(client, opened):
    rfq, qs = opened
    r = rows(comparison(client, rfq))
    a = r["Acme Supplies"]["scores"]
    assert (a["price"], a["delivery"], a["compliance"], a["terms"], a["total"]) == ("95.57", "100.00", None, None, None)
    assert a["missing"] == ["compliance score", "terms score"]
    assert r["Cedar Co"]["scores"]["price"] is None and "Some items are not quoted" in r["Cedar Co"]["scores"]["missing"]


def test_evaluation_adds_manual_scores_and_the_weighted_total_and_rank(client, opened):
    rfq, qs = opened
    assert evaluate(client, rfq, qs["a"], 8, 6).status_code == 200
    assert evaluate(client, rfq, qs["b"], 7, 9).status_code == 200
    r = rows(comparison(client, rfq))
    assert (r["Acme Supplies"]["scores"]["total"], r["Acme Supplies"]["rank"]) == ("87.23", 1)
    assert (r["Bravo Traders"]["scores"]["total"], r["Bravo Traders"]["rank"]) == ("84.33", 2)
    ev = r["Acme Supplies"]["evaluation"]
    assert ev["compliance_score"] == 8 and ev["terms_note"] == "Net 30, delivery included." and ev["evaluator_name"] == "Pat Procurement" and ev["version"] == 1
    assert [x["vendor_name"] for x in comparison(client, rfq)["quotations"]][:2] == ["Acme Supplies", "Bravo Traders"]  # best first


def test_quotations_in_different_currencies_are_never_treated_as_equivalent(client, issued, quote, clock):
    rfq = issued()
    quote(VA, rfq, ("23000.00", "700.00"))
    quote(VB, rfq, ("250.00", "8.00"), currency="USD", lead=10)
    clock.advance(days=3)
    c = comparison(client, rfq)
    r = rows(c)
    assert c["mixed_currencies"] is True and c["currencies"] == ["INR", "USD"] and "nothing is converted" in c["note"]
    assert r["Bravo Traders"]["currency"] == "USD" and r["Bravo Traders"]["total_amount"] == "1032.00"
    assert r["Bravo Traders"]["scores"]["price"] == "100.00" and r["Acme Supplies"]["scores"]["price"] == "100.00"  # each alone in its own currency
    assert r["Bravo Traders"]["within_budget"] is None and r["Acme Supplies"]["within_budget"] is True  # the budget is in rupees
    assert r["Bravo Traders"]["lowest_price"] is True  # lowest within USD only


def test_the_comparison_still_works_if_the_vendor_service_is_down_but_says_so(client, opened, world):
    rfq, _ = opened
    world.vendor_down = True
    c = comparison(client, rfq)
    assert c["vendor_info_available"] is False and all(q["vendor_status"] is None for q in c["quotations"]) and len(c["quotations"]) == 3


def test_an_empty_comparison_is_valid(client, issued, clock):
    rfq = issued()
    clock.advance(days=3)
    c = comparison(client, rfq)
    assert c["quotations"] == [] and c["currencies"] == [] and c["can_select"] is True


def test_the_comparison_is_for_procurement_only(client, opened):
    rfq, _ = opened
    for h in (VA, VB):
        assert client.get(f"{RFQ}/{rfq['id']}{CMP}", headers=h).status_code == 403


# ---- evaluation ------------------------------------------------------------------------------------
@pytest.mark.parametrize("body", [{}, {"compliance_score": 11, "compliance_note": "x"}, {"compliance_score": -1, "compliance_note": "x"}, {"compliance_score": 5},
                                  {"terms_score": 5}, {"terms_score": 5, "terms_note": " "}, {"compliance_score": 5.5, "compliance_note": "x"},
                                  {"compliance_score": 5, "compliance_note": "x" * 1001}])
def test_invalid_evaluations_are_refused(client, opened, body):
    rfq, qs = opened
    assert client.put(f"{RFQ}/{rfq['id']}/evaluations/{qs['a']['id']}", headers=PROC, json=body).status_code == 422


def test_an_evaluation_is_updated_only_with_the_version_it_was_loaded_at(client, opened):
    rfq, qs = opened
    assert evaluate(client, rfq, qs["a"], 5, None).status_code == 200
    assert evaluate(client, rfq, qs["a"], 6, None).status_code == 409  # no version: someone else may have changed it
    ok = evaluate(client, rfq, qs["a"], 6, 7, version=1)
    assert ok.status_code == 200 and ok.json()["version"] == 2 and ok.json()["terms_score"] == 7
    assert evaluate(client, rfq, qs["a"], 9, 9, version=1).status_code == 409


def test_a_manual_score_can_be_cleared_and_zero_is_a_real_score(client, opened):
    rfq, qs = opened
    evaluate(client, rfq, qs["a"], 0, 10)
    out = evaluate(client, rfq, qs["a"], None, 10, version=1)
    assert out.status_code == 200 and out.json()["compliance_score"] is None
    assert rows(comparison(client, rfq))["Acme Supplies"]["scores"]["compliance"] is None
    evaluate(client, rfq, qs["a"], 0, 10, version=2)
    assert rows(comparison(client, rfq))["Acme Supplies"]["scores"]["compliance"] == "0.00"


def test_evaluating_is_refused_while_sealed_and_for_an_unknown_quotation(client, rfq_with_quotes, clock):
    rfq, qs = rfq_with_quotes
    assert evaluate(client, rfq, qs["a"], 5, 5).status_code == 409  # still sealed
    clock.advance(days=3)
    assert client.put(f"{RFQ}/{rfq['id']}/evaluations/nope", headers=PROC, json={"compliance_score": 1, "compliance_note": "x"}).status_code == 404


def test_evaluations_are_recorded_in_the_history_and_locked_after_the_award(client, opened):
    rfq, qs = opened
    evaluate(client, rfq, qs["a"], 8, 6)
    assert client.get(f"{RFQ}/{rfq['id']}", headers=PROC).json()["history"][-1]["action"] == "evaluated"
    client.post(f"{RFQ}/{rfq['id']}/selection", headers=PROC, json={"quotation_id": qs["a"]["id"], "justification": "Best balance of price and speed."})
    locked = evaluate(client, rfq, qs["a"], 1, 1, version=1)
    assert locked.status_code == 409 and "locked" in locked.json()["detail"]


# ---- selection -------------------------------------------------------------------------------------
def select(client, rfq, q, text="Best balance of price and delivery time.", h=PROC, **extra):
    return client.post(f"{RFQ}/{rfq['id']}/selection", headers=h, json={"quotation_id": q["id"], "justification": text, **extra})


def test_selection_is_refused_before_the_deadline_unless_the_rfq_is_closed(client, rfq_with_quotes):
    rfq, qs = rfq_with_quotes
    r = select(client, rfq, qs["a"])
    assert r.status_code == 409 and "deadline has not passed" in r.json()["detail"]
    client.post(f"{RFQ}/{rfq['id']}/close", headers=PROC)
    assert select(client, rfq, qs["a"]).status_code == 200


def test_selecting_a_supplier_awards_the_rfq_and_records_who_when_and_why(client, opened, db):
    rfq, qs = opened
    evaluate(client, rfq, qs["a"], 8, 6)
    evaluate(client, rfq, qs["b"], 7, 9)
    r = select(client, rfq, qs["a"], "Highest overall score and fastest delivery.")
    assert r.status_code == 200, r.text
    sel = r.json()
    assert sel["status"] == "awarded" and sel["vendor_name"] == "Acme Supplies" and sel["total_amount"] == "94800.00" and sel["currency"] == "INR"
    assert sel["selected_by_name"] == "Pat Procurement" and sel["selected_at"].endswith("Z") and sel["justification"] == "Highest overall score and fastest delivery."
    assert sel["acknowledged_missing_items"] is False and "vendor_id" in sel
    out = client.get(f"{RFQ}/{rfq['id']}", headers=PROC).json()
    assert out["status"] == "awarded" and out["selection"]["id"] == sel["id"] and out["actions"] == ["compare", "revoke"]
    assert [h["action"] for h in out["history"]][-3:] == ["evaluated", "closed", "awarded"] and out["history"][-2]["note"] == "Closed automatically because the deadline passed"
    snap = json.loads(db.query(Selection).one().score_snapshot)
    assert snap["scores"]["total"] == "87.23" and snap["rank"] == 1 and snap["vendor_status"] == "verified" and snap["weights"]["price"] == 40
    assert snap["evaluation"]["compliance_score"] == 8 and snap["compared_quotations"] == 3
    assert client.get(f"{RFQ}/{rfq['id']}/selection", headers=PROC).json()["id"] == sel["id"]
    assert db.query(QuotationEvent).filter_by(type="supplier_selected").count() == 1


def test_vendors_learn_the_outcome_of_their_own_quotation_only(client, opened):
    rfq, qs = opened
    select(client, rfq, qs["b"])
    assert client.get(f"{QUO}/{qs['b']['id']}", headers=VB).json()["status"] == "selected"
    assert client.get(f"{QUO}/{qs['a']['id']}", headers=VA).json()["status"] == "not_selected"
    assert client.get(f"{QUO}/{qs['a']['id']}", headers=VB).status_code == 404
    text = client.get(f"{QUO}/{qs['a']['id']}", headers=VA).text
    assert "Best balance" not in text and "justification" not in text and "90600" not in text  # nothing about the winner's terms


@pytest.mark.parametrize("text", ["", "short", "         ", "x" * 2001])
def test_a_justification_is_required(client, opened, text):
    rfq, qs = opened
    assert select(client, rfq, qs["a"], text).status_code == 422


def test_only_a_submitted_quotation_of_this_rfq_can_be_selected(client, opened, issued, quote, world):
    rfq, qs = opened
    assert select(client, rfq, {"id": "nope"}).status_code == 422
    assert client.post(f"{RFQ}/{rfq['id']}/selection", headers=PROC, json={"justification": "A long enough reason."}).status_code == 422


def test_a_quotation_from_another_rfq_cannot_be_selected(client, opened, world, quote, make_rfq, clock):
    rfq, qs = opened
    world.add_request("pr-2", "PR-2026-000002")
    other = make_rfq(purchase_request_id="pr-2")
    client.post(f"{RFQ}/{other['id']}/invitations", headers=PROC, json={"vendor_ids": ["v-a"]})
    client.post(f"{RFQ}/{other['id']}/publish", headers=PROC)
    foreign = quote(VA, {**other}, ("1.00", "1.00"))
    r = select(client, rfq, foreign)
    assert r.status_code == 422


def test_a_vendor_that_is_no_longer_verified_cannot_be_awarded(client, opened, world):
    rfq, qs = opened
    world.vendors["v-a"]["status"] = "suspended"
    r = select(client, rfq, qs["a"])
    assert r.status_code == 409 and "suspended" in r.json()["detail"] and "Acme Supplies" in r.json()["detail"]
    assert client.get(f"{RFQ}/{rfq['id']}", headers=PROC).json()["status"] in ("issued", "closed")  # nothing was awarded
    assert select(client, rfq, qs["b"]).status_code == 200


def test_selection_needs_the_vendor_service_to_check_eligibility(client, opened, world):
    rfq, qs = opened
    world.vendor_down = True
    r = select(client, rfq, qs["a"])
    assert r.status_code == 503 and "not available" in r.json()["detail"]
    assert client.get(f"{RFQ}/{rfq['id']}", headers=PROC).json()["selection"] is None


def test_a_quotation_with_missing_items_needs_an_explicit_acknowledgement(client, opened):
    rfq, qs = opened
    r = select(client, rfq, qs["c"])
    assert r.status_code == 422 and "does not price items 2" in r.json()["detail"]
    ok = select(client, rfq, qs["c"], acknowledge_missing_items=True)
    assert ok.status_code == 200 and ok.json()["acknowledged_missing_items"] is True and ok.json()["total_amount"] == "96000.00"


def test_repeating_the_same_selection_is_harmless_but_a_different_one_conflicts(client, opened, db):
    rfq, qs = opened
    first = select(client, rfq, qs["a"]).json()
    again = select(client, rfq, qs["a"])
    assert again.status_code == 200 and again.json()["id"] == first["id"]
    assert db.query(Selection).count() == 1 and db.query(QuotationEvent).filter_by(type="supplier_selected").count() == 1
    other = select(client, rfq, qs["b"])
    assert other.status_code == 409 and "already awarded to Acme Supplies" in other.json()["detail"]
    assert db.query(Selection).count() == 1


def test_the_database_refuses_a_second_final_award_even_if_the_checks_are_bypassed(client, opened, db):
    """Two requests that both pass the application checks cannot both succeed: the unique index on active_rfq_id decides."""
    from sqlalchemy.exc import IntegrityError
    rfq, qs = opened
    sel = select(client, rfq, qs["a"]).json()
    dup = Selection(rfq_id=rfq["id"], quotation_id=qs["b"]["id"], vendor_id="v-b", vendor_name="Bravo Traders", active_rfq_id=rfq["id"], justification="Second award",
                    currency="INR", total_amount=1, score_snapshot="{}", selected_by_id="x", selected_by_name="X")
    db.add(dup)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    assert db.query(Selection).filter_by(status="awarded").count() == 1 and sel["status"] == "awarded"


def test_a_race_past_the_checks_is_a_409_not_a_500(client, opened, monkeypatch, db):
    from sqlalchemy import text

    from app import evaluation
    rfq, qs = opened
    assert select(client, rfq, qs["a"]).status_code == 200
    # Show the second request the world as it was before the first award committed: RFQ closed, no active selection, quotations still submitted.
    db.execute(text("UPDATE quotations SET status = 'submitted'"))
    db.commit()
    real = evaluation.get_rfq

    def stale_view(db, rfq_id, lock=False):
        r = real(db, rfq_id, lock=lock)
        r.status = "closed"
        return r
    monkeypatch.setattr(evaluation, "get_rfq", stale_view)
    monkeypatch.setattr(evaluation, "active_selection", lambda db, rfq_id: None)
    r = select(client, rfq, qs["b"])
    assert r.status_code == 409 and "already has an award" in r.json()["detail"]


@pytest.mark.skipif(not os.environ.get("TEST_DATABASE_URL"), reason="needs a real MySQL server to race two requests")
def test_two_people_selecting_at_the_same_moment_produce_exactly_one_award(client, opened, db):
    rfq, qs = opened
    results = []
    barrier = threading.Barrier(2)

    def go(h, q):
        barrier.wait()
        results.append(select(client, rfq, q, h=h).status_code)
    threads = [threading.Thread(target=go, args=(PROC, qs["a"])), threading.Thread(target=go, args=(PROC2, qs["b"]))]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert sorted(results) == [200, 409]
    assert db.query(Selection).filter_by(status="awarded").count() == 1


def test_selection_is_refused_for_an_rfq_in_the_wrong_state(client, make_rfq, issued, clock):
    draft = make_rfq()
    assert client.post(f"{RFQ}/{draft['id']}/selection", headers=PROC, json={"quotation_id": "x", "justification": "A long enough reason."}).status_code == 409
    client.post(f"{RFQ}/{draft['id']}/cancel", headers=PROC, json={"reason": "No longer needed"})
    assert client.post(f"{RFQ}/{draft['id']}/selection", headers=PROC, json={"quotation_id": "x", "justification": "A long enough reason."}).status_code == 409


def test_revoking_an_award_reopens_the_choice_and_keeps_the_history(client, opened):
    rfq, qs = opened
    first = select(client, rfq, qs["a"]).json()
    assert client.post(f"{RFQ}/{rfq['id']}/selection/revoke", headers=PROC, json={"reason": "x"}).status_code == 422
    rv = client.post(f"{RFQ}/{rfq['id']}/selection/revoke", headers=PROC, json={"reason": "Vendor could not confirm stock."})
    assert rv.status_code == 200 and rv.json()["status"] == "revoked" and rv.json()["revoke_reason"] == "Vendor could not confirm stock." and rv.json()["revoked_by_name"] == "Pat Procurement"
    out = client.get(f"{RFQ}/{rfq['id']}", headers=PROC).json()
    assert out["status"] == "closed" and out["selection"] is None and out["history"][-1]["action"] == "award_revoked"
    assert client.get(f"{RFQ}/{rfq['id']}/selection", headers=PROC).status_code == 404
    assert client.get(f"{QUO}/{qs['a']['id']}", headers=VA).json()["status"] == "submitted"  # outcomes reset
    second = select(client, rfq, qs["b"], "Next best option after the first fell through.")
    assert second.status_code == 200 and second.json()["id"] != first["id"]
    hist = client.get(f"{RFQ}/{rfq['id']}/selection/history", headers=PROC).json()["items"]
    assert [(h["seq"], h["vendor_name"], h["status"]) for h in hist] == [(1, "Acme Supplies", "revoked"), (2, "Bravo Traders", "awarded")]
    assert client.post(f"{RFQ}/{rfq['id']}/selection/revoke", headers=PROC, json={"reason": "Again please"}).status_code == 200
    assert client.post(f"{RFQ}/{rfq['id']}/selection/revoke", headers=PROC, json={"reason": "Nothing left"}).status_code == 409


def test_an_awarded_rfq_cannot_be_cancelled_or_changed(client, opened):
    rfq, qs = opened
    select(client, rfq, qs["a"])
    assert client.post(f"{RFQ}/{rfq['id']}/cancel", headers=PROC, json={"reason": "Changed our minds"}).status_code == 409
    assert client.post(f"{RFQ}/{rfq['id']}/close", headers=PROC).status_code == 409
    assert client.post(f"{RFQ}/{rfq['id']}/invitations", headers=PROC, json={"vendor_ids": ["v-x"]}).status_code == 409


# ---- the contract Phase 7 will use -----------------------------------------------------------------
def test_the_award_contract_has_everything_a_purchase_order_needs(client, opened):
    rfq, qs = opened
    evaluate(client, rfq, qs["a"], 8, 6)
    sel = select(client, rfq, qs["a"]).json()
    r = client.get(f"/internal/v1/rfqs/{rfq['id']}/award", headers=svc_header("purchase-order-service"))
    assert r.status_code == 200, r.text
    from procurehub_common.contracts.quotation import AwardRef
    a = AwardRef.model_validate(r.json())
    assert a.selection_id == sel["id"] and a.rfq_number == rfq["number"] and a.purchase_request_number == "PR-2026-000001" and a.vendor_id == "v-a" and a.vendor_name == "Acme Supplies"
    assert str(a.total_amount) == "94800.00" and a.currency == "INR" and a.lead_time_days == 14 and a.terms == "Delivery included." and a.payment_terms_days == 30
    assert [(i.line_no, str(i.quantity), i.unit, str(i.unit_price), str(i.line_total)) for i in a.items] == [(1, "4.000", "each", "23000.0000", "92000.00"), (2, "4.000", "each", "700.0000", "2800.00")]
    assert a.items[0].description == "14-inch laptop" and a.justification and a.selected_by_name == "Pat Procurement"
    assert "estimated_unit_price" not in r.text and "budget" not in r.text


def test_the_award_contract_is_404_until_awarded_and_after_a_revoke(client, opened):
    rfq, qs = opened
    url = f"/internal/v1/rfqs/{rfq['id']}/award"
    assert client.get(url, headers=svc_header("purchase-order-service")).status_code == 404
    select(client, rfq, qs["a"])
    assert client.get(url, headers=svc_header("purchase-order-service")).status_code == 200
    client.post(f"{RFQ}/{rfq['id']}/selection/revoke", headers=PROC, json={"reason": "Withdrawn by the vendor."})
    assert client.get(url, headers=svc_header("purchase-order-service")).status_code == 404
    assert client.get("/internal/v1/rfqs/nope/award", headers=svc_header("purchase-order-service")).status_code == 404


def test_the_award_contract_is_for_listed_services_with_the_right_secret_only(client, opened):
    rfq, qs = opened
    select(client, rfq, qs["a"])
    url = f"/internal/v1/rfqs/{rfq['id']}/award"
    for h in ({}, PROC, VA, svc_header("quotation-service"), svc_header("approval-service"), svc_header("random-service"), svc_header("purchase-order-service", "z" * 40)):
        assert client.get(url, headers=h).status_code == 401, h
