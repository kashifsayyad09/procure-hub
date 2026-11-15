"""The Phase 6 hand-off across five real services, with tokens from the real auth service:
employee request -> manager approval -> RFQ -> invited vendors quote -> sealed until the deadline -> comparison -> evaluation -> selection."""
import time
from datetime import UTC, datetime, timedelta

import pytest

from conftest import wait_until

pytestmark = pytest.mark.e2e

PR, AP, VN, RFQ, QUO = "/api/v1/purchase-requests", "/api/v1/approvals", "/api/v1/vendors", "/api/v1/rfqs", "/api/v1/quotations"


def verified_vendor(stack, email, name, tax_id):
    """A vendor registers, submits, and a second reviewer verifies, all through the real vendor service."""
    t = stack.tokens[email]
    body = {"legal_name": name, "tax_id": tax_id, "address_line1": "1 Industrial Road", "city": "Pune", "country": "IN", "categories": ["it_hardware"],
            "contacts": [{"name": name, "email": email}]}
    v = stack.call("vendor", "POST", VN, t, json=body)
    assert v.status_code == 201, v.text
    sub = stack.call("vendor", "POST", f"{VN}/{v.json()['id']}/submit", t).json()
    ok = stack.call("vendor", "POST", f"{VN}/{sub['id']}/verify", stack.tokens["paul@example.com"], json={"version": sub["version"]})
    assert ok.status_code == 200 and ok.json()["status"] == "verified", ok.text
    return sub["id"]


def approved_request(stack, title):
    t = stack.tokens["erin@example.com"]
    body = {"title": title, "justification": "Needed", "department": "Design", "priority": "normal", "currency": "INR",
            "items": [{"description": "Laptop", "quantity": "4", "unit": "each", "unit_price": "24000.00"},
                      {"description": "Sleeve", "quantity": "4", "unit": "each", "unit_price": "750.50"}]}
    r = stack.call("pr", "POST", PR, t, json=body).json()
    stack.call("pr", "POST", f"{PR}/{r['id']}/submit", t)
    ap = wait_until(lambda: next((a for a in stack.call("approval", "GET", AP, stack.tokens["mia@example.com"], params={"view": "all", "page_size": 100}).json()["items"]
                                  if a["request_id"] == r["id"]), None), message="the approval to appear")
    d = stack.call("approval", "POST", f"{AP}/{ap['id']}/approve", stack.tokens["mia@example.com"], json={})
    assert d.status_code == 200, d.text
    wait_until(lambda: stack.call("pr", "GET", f"{PR}/{r['id']}", t).json()["status"] == "approved", message="the request to be approved")
    return r["id"]


def test_the_whole_sourcing_flow_across_real_services(stack):
    pat, wendy, valerie, vince = (stack.tokens[e] for e in ("pat@example.com", "wendy@example.com", "valerie@example.com", "vince@example.com"))
    assert stack.call("quotation", "GET", f"{RFQ}/invited", wendy).status_code == 403  # a vendor user with no company profile yet
    verified_vendor(stack, "wendy@example.com", "Wendy Wholesale", "WENDY0000001")  # registered and verified, but never invited
    va = verified_vendor(stack, "valerie@example.com", "Valerie Supplies", "VALERIE0001")
    vi = verified_vendor(stack, "vince@example.com", "Vince Traders", "VINCE000001")
    rid = approved_request(stack, "Design team laptops")

    # procurement sees the approved request as eligible, and a draft request is not
    eligible = stack.call("quotation", "GET", f"{RFQ}/eligible-requests", pat).json()
    assert rid in [i["id"] for i in eligible["items"]] and all(i["rfq_id"] is None for i in eligible["items"] if i["id"] == rid)
    unapproved = {"title": "Not yet", "justification": "x", "department": "D", "priority": "low", "currency": "INR",
                  "items": [{"description": "Pen", "quantity": "1", "unit": "each", "unit_price": "1.00"}]}
    draft = stack.call("pr", "POST", PR, stack.tokens["erin@example.com"], json=unapproved).json()
    refused = stack.call("quotation", "POST", RFQ, pat, json={"purchase_request_id": draft["id"], "deadline": (datetime.now(UTC) + timedelta(minutes=5)).isoformat()})
    assert refused.status_code == 422 and "Only approved" in refused.json()["detail"]

    deadline = datetime.now(UTC) + timedelta(seconds=14)
    rfq = stack.call("quotation", "POST", RFQ, pat, json={"purchase_request_id": rid, "description": "Laptops", "requirements": "3 year warranty",
                                                          "deadline": deadline.isoformat()})
    assert rfq.status_code == 201, rfq.text
    rfq = rfq.json()
    assert rfq["budget_amount"] == "99002.00" and len(rfq["items"]) == 2
    assert stack.call("quotation", "POST", RFQ, pat, json={"purchase_request_id": rid, "deadline": deadline.isoformat()}).status_code == 409  # one live RFQ per request

    inv = stack.call("quotation", "POST", f"{RFQ}/{rfq['id']}/invitations", pat, json={"vendor_ids": [va, vi]})
    assert inv.status_code == 201, inv.text
    assert stack.call("quotation", "GET", f"{RFQ}/invited", valerie).json()["total"] == 0  # not visible until issued
    assert stack.call("quotation", "POST", f"{RFQ}/{rfq['id']}/publish", pat).json()["status"] == "issued"

    mine = stack.call("quotation", "GET", f"{RFQ}/invited", valerie).json()
    assert mine["total"] == 1 and mine["items"][0]["id"] == rfq["id"]
    detail = stack.call("quotation", "GET", f"{RFQ}/invited/{rfq['id']}", valerie)
    assert "budget" not in detail.text and "estimated" not in detail.text and "99002" not in detail.text
    assert stack.call("quotation", "GET", f"{RFQ}/invited", wendy).json()["total"] == 0  # wendy's company was never invited
    assert stack.call("quotation", "GET", f"{RFQ}/invited/{rfq['id']}", wendy).status_code == 404

    def quote(token, prices, lead):
        items = detail.json()["items"]
        body = {"rfq_id": rfq["id"], "currency": "INR", "lead_time_days": lead, "valid_until": str((datetime.now(UTC) + timedelta(days=60)).date()), "payment_terms_days": 30,
                "items": [{"rfq_item_id": it["id"], "unit_price": p} for it, p in zip(items, prices, strict=True)]}
        q = stack.call("quotation", "POST", QUO, token, json=body)
        assert q.status_code == 201, q.text
        s = stack.call("quotation", "POST", f"{QUO}/{q.json()['id']}/submit", token)
        assert s.status_code == 200, s.text
        return s.json()
    qa = quote(valerie, ("23000.00", "700.00"), 14)
    qb = quote(vince, ("22000.00", "650.00"), 21)
    assert qa["total_amount"] == "94800.00" and qb["total_amount"] == "90600.00"
    assert stack.call("quotation", "GET", f"{QUO}/{qa['id']}", vince).status_code == 404  # a vendor cannot read a competitor's quotation

    # sealed while bidding is open
    sealed = stack.call("quotation", "GET", f"{RFQ}/{rfq['id']}/quotations", pat).json()
    assert sealed["quotations_open"] is False and all(r["total_amount"] is None for r in sealed["rows"]) and {r["status"] for r in sealed["rows"]} == {"submitted"}
    assert stack.call("quotation", "GET", f"{RFQ}/{rfq['id']}/comparison", pat).status_code == 409

    time.sleep(max(0, (deadline - datetime.now(UTC)).total_seconds()) + 1.5)
    late = stack.call("quotation", "POST", f"{QUO}/{qa['id']}/withdraw", valerie)
    assert late.status_code == 409  # too late to change a submission

    cmp = stack.call("quotation", "GET", f"{RFQ}/{rfq['id']}/comparison", pat).json()
    by = {q["vendor_name"]: q for q in cmp["quotations"]}
    assert by["Vince Traders"]["lowest_price"] is True and by["Valerie Supplies"]["fastest"] is True and by["Valerie Supplies"]["vendor_status"] == "verified"
    for q, comp, terms in ((qa, 8, 6), (qb, 7, 9)):
        ev = stack.call("quotation", "PUT", f"{RFQ}/{rfq['id']}/evaluations/{q['id']}", pat,
                        json={"compliance_score": comp, "compliance_note": "Checked against the specification.", "terms_score": terms, "terms_note": "Reviewed the terms."})
        assert ev.status_code == 200, ev.text
    ranked = stack.call("quotation", "GET", f"{RFQ}/{rfq['id']}/comparison", pat).json()["quotations"]
    assert [(q["vendor_name"], q["rank"], q["scores"]["total"]) for q in ranked] == [("Valerie Supplies", 1, "87.23"), ("Vince Traders", 2, "84.33")]

    sel = stack.call("quotation", "POST", f"{RFQ}/{rfq['id']}/selection", pat, json={"quotation_id": qa["id"], "justification": "Best overall score and fastest delivery."})
    assert sel.status_code == 200, sel.text
    assert sel.json()["vendor_name"] == "Valerie Supplies" and sel.json()["selected_by_name"] == "Pat Procurement"
    other = stack.call("quotation", "POST", f"{RFQ}/{rfq['id']}/selection", stack.tokens["paul@example.com"],
                       json={"quotation_id": qb["id"], "justification": "A different choice entirely."})
    assert other.status_code == 409
    assert stack.call("quotation", "GET", f"{QUO}/{qa['id']}", valerie).json()["status"] == "selected"
    assert stack.call("quotation", "GET", f"{QUO}/{qb['id']}", vince).json()["status"] == "not_selected"
    assert stack.call("quotation", "GET", f"{RFQ}/{rfq['id']}", pat).json()["status"] == "awarded"
    assert stack.call("quotation", "GET", f"{RFQ}/{rfq['id']}/selection/history", pat).json()["items"][0]["status"] == "awarded"


def test_a_vendor_suspended_after_the_invitation_cannot_quote(stack):
    pat, paul, walt = stack.tokens["pat@example.com"], stack.tokens["paul@example.com"], stack.tokens["walt@example.com"]
    vendor_id = verified_vendor(stack, "walt@example.com", "Walt Works", "WALT00000001")
    rid = approved_request(stack, "Suspension check")
    rfq = stack.call("quotation", "POST", RFQ, pat, json={"purchase_request_id": rid, "deadline": (datetime.now(UTC) + timedelta(minutes=30)).isoformat()}).json()
    assert stack.call("quotation", "POST", f"{RFQ}/{rfq['id']}/invitations", pat, json={"vendor_ids": [vendor_id]}).status_code == 201
    assert stack.call("quotation", "POST", f"{RFQ}/{rfq['id']}/publish", pat).status_code == 200
    cur = stack.call("vendor", "GET", f"{VN}/{vendor_id}", paul).json()
    assert stack.call("vendor", "POST", f"{VN}/{vendor_id}/suspend", paul, json={"version": cur["version"], "reason": "Failed quality audit"}).status_code == 200
    d = stack.call("quotation", "GET", f"{RFQ}/invited/{rfq['id']}", walt).json()
    assert d["can_quote"] is False and "not verified" in d["blocked_reason"]
    q = stack.call("quotation", "POST", QUO, walt, json={"rfq_id": rfq["id"], "currency": "INR", "items": [{"rfq_item_id": d["items"][0]["id"], "unit_price": "1.00"}]})
    assert q.status_code == 403
    stack.call("quotation", "POST", f"{RFQ}/{rfq['id']}/cancel", pat, json={"reason": "Test finished"})


def test_the_award_contract_can_be_read_by_a_service_token_only(stack):
    import httpx
    from procurehub_common.service_auth import create_service_token
    pat = stack.tokens["pat@example.com"]
    awarded = next(r for r in stack.call("quotation", "GET", RFQ, pat, params={"status": "awarded"}).json()["items"])
    secret = stack.base_env["INTERNAL_JWT_SECRET"]
    token = create_service_token(secret, "purchase-order-service")
    url = stack.url("quotation") + f"/internal/v1/rfqs/{awarded['id']}/award"
    ok = httpx.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=10)
    assert ok.status_code == 200 and ok.json()["vendor_name"] == "Valerie Supplies" and ok.json()["total_amount"] == "94800.00" and len(ok.json()["items"]) == 2
    assert stack.call("quotation", "GET", f"/internal/v1/rfqs/{awarded['id']}/award", pat).status_code == 401
