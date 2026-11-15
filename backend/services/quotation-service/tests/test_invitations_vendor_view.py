from datetime import timedelta

from app.models import QuotationEvent
from tests.conftest import PROC, QUO, RFQ, VA, VB, VC, VNONE, VX, headers

INV = "/invitations"


def invite(client, rfq, ids, h=PROC):
    return client.post(f"{RFQ}/{rfq['id']}{INV}", headers=h, json={"vendor_ids": ids})


def test_verified_vendors_are_invited_and_recorded(client, make_rfq, db):
    rfq = make_rfq()
    r = invite(client, rfq, ["v-a", "v-b"])
    assert r.status_code == 201
    invs = r.json()["invitations"]
    assert [(i["vendor_name"], i["status"], i["sent_at"]) for i in invs] == [("Acme Supplies", "invited", None), ("Bravo Traders", "invited", None)]  # not sent until issued
    assert invs[0]["invited_by_name"] == "Pat Procurement" and r.json()["history"][-1]["action"] == "vendors_invited"
    assert db.query(QuotationEvent).filter_by(type="vendors_invited").count() == 1


def test_only_verified_vendors_can_be_invited(client, make_rfq):
    rfq = make_rfq()
    r = invite(client, rfq, ["v-a", "v-x"])
    assert r.status_code == 422 and "Xenon Pending Ltd" in r.json()["detail"] and "Acme" not in r.json()["detail"]
    assert client.get(f"{RFQ}/{rfq['id']}", headers=PROC).json()["invitations"] == []  # all or nothing


def test_unknown_vendors_are_refused(client, make_rfq):
    r = invite(client, make_rfq(), ["v-a", "ghost"])
    assert r.status_code == 422 and "ghost" in r.json()["detail"]


def test_a_vendor_cannot_be_invited_twice(client, make_rfq):
    rfq = make_rfq()
    assert invite(client, rfq, ["v-a"]).status_code == 201
    again = invite(client, rfq, ["v-a", "v-b"])
    assert again.status_code == 409 and "Acme Supplies" in again.json()["detail"]
    assert len(client.get(f"{RFQ}/{rfq['id']}", headers=PROC).json()["invitations"]) == 1  # v-b was not added either
    assert invite(client, rfq, ["v-b", "v-b"]).status_code == 201  # a repeated id in one request is just one invitation
    assert len(client.get(f"{RFQ}/{rfq['id']}", headers=PROC).json()["invitations"]) == 2


def test_invitation_input_is_validated(client, make_rfq):
    rfq = make_rfq()
    for ids in ([], [""], ["x" * 37], ["v-a"] * 0 + ["a"] * 51):
        assert invite(client, rfq, ids).status_code == 422, ids


def test_a_withdrawn_invitation_can_be_sent_again_without_duplicating(client, make_rfq):
    rfq = make_rfq()
    out = invite(client, rfq, ["v-a"]).json()
    inv_id = out["invitations"][0]["id"]
    w = client.post(f"{RFQ}/{rfq['id']}{INV}/{inv_id}/withdraw", headers=PROC)
    assert w.status_code == 200 and w.json()["invitations"][0]["status"] == "withdrawn" and w.json()["invitations"][0]["withdrawn_at"]
    assert client.post(f"{RFQ}/{rfq['id']}{INV}/{inv_id}/withdraw", headers=PROC).status_code == 409
    back = invite(client, rfq, ["v-a"]).json()
    assert len(back["invitations"]) == 1 and back["invitations"][0]["status"] == "invited" and back["invitations"][0]["withdrawn_at"] is None
    assert client.post(f"{RFQ}/{rfq['id']}{INV}/nope/withdraw", headers=PROC).status_code == 404


def test_inviting_after_issue_sends_immediately_but_not_after_the_deadline(client, issued, clock):
    rfq = issued(vendors=("v-a",))
    late = invite(client, rfq, ["v-b"]).json()
    assert next(i for i in late["invitations"] if i["vendor_id"] == "v-b")["sent_at"]
    assert client.get(f"{RFQ}/invited", headers=VB).json()["total"] == 1
    clock.advance(days=3)
    r = invite(client, rfq, ["v-c"])
    assert r.status_code == 409 and "before its deadline" in r.json()["detail"]


def test_a_vendor_sees_only_rfqs_they_were_invited_to_and_only_once_issued(client, make_rfq, issued, world, clock):
    draft = make_rfq()
    invite(client, draft, ["v-a"])
    assert client.get(f"{RFQ}/invited", headers=VA).json()["total"] == 0  # invited but not yet sent
    assert client.get(f"{RFQ}/invited/{draft['id']}", headers=VA).status_code == 404
    client.post(f"{RFQ}/{draft['id']}/publish", headers=PROC)
    mine = client.get(f"{RFQ}/invited", headers=VA).json()
    assert mine["total"] == 1 and mine["items"][0]["id"] == draft["id"] and mine["items"][0]["can_quote"] is True and mine["items"][0]["quotation"] is None
    assert client.get(f"{RFQ}/invited", headers=VB).json()["total"] == 0
    assert client.get(f"{RFQ}/invited/{draft['id']}", headers=VB).status_code == 404
    assert client.get(f"{RFQ}/invited/{draft['id']}", headers=VC).status_code == 404


def test_a_vendor_never_sees_budgets_estimates_or_other_vendors(client, issued):
    rfq = issued()
    text = client.get(f"{RFQ}/invited/{rfq['id']}", headers=VA).text + client.get(f"{RFQ}/invited", headers=VA).text
    for secret in ("budget", "estimated_unit_price", "99002", "24000", "750.5", "Bravo", "Cedar", "v-b", "v-c", "invited_by", "history", "Pat Procurement"):
        assert secret not in text, secret
    detail = client.get(f"{RFQ}/invited/{rfq['id']}", headers=VA).json()
    assert detail["description"] and detail["requirements"] and [i["line_no"] for i in detail["items"]] == [1, 2] and detail["items"][0]["quantity"] == "4.000"


def test_the_vendor_is_identified_by_the_token_not_by_anything_the_browser_sends(client, issued):
    rfq = issued(vendors=("v-a",))
    spoof = {**VB}
    r = client.get(f"{RFQ}/invited?vendor_id=v-a", headers=spoof)
    assert r.json()["total"] == 0
    assert client.get(f"{RFQ}/invited/{rfq['id']}?vendor_id=v-a", headers={**spoof, "X-Vendor-Id": "v-a"}).status_code == 404


def test_a_vendor_whose_invitation_is_withdrawn_loses_access(client, issued):
    rfq = issued(vendors=("v-a", "v-b"))
    inv = next(i for i in rfq["invitations"] if i["vendor_id"] == "v-a")
    client.post(f"{RFQ}/{rfq['id']}{INV}/{inv['id']}/withdraw", headers=PROC)
    assert client.get(f"{RFQ}/invited", headers=VA).json()["total"] == 0
    assert client.get(f"{RFQ}/invited/{rfq['id']}", headers=VA).status_code == 404
    assert client.get(f"{RFQ}/invited/{rfq['id']}", headers=VB).status_code == 200


def test_a_vendor_can_decline_and_then_cannot_quote(client, issued, quote):
    rfq = issued(vendors=("v-a",))
    d = client.post(f"{RFQ}/invited/{rfq['id']}/decline", headers=VA)
    assert d.status_code == 200 and d.json()["invitation_status"] == "declined" and d.json()["can_quote"] is False and "declined" in d.json()["blocked_reason"]
    assert client.post(f"{RFQ}/invited/{rfq['id']}/decline", headers=VA).status_code == 409
    body = {"rfq_id": rfq["id"], "currency": "INR", "items": []}
    assert client.post(QUO, headers=VA, json=body).status_code == 409
    assert client.get(f"{RFQ}/{rfq['id']}", headers=PROC).json()["invitations"][0]["status"] == "declined"


def test_a_vendor_who_has_submitted_must_withdraw_before_declining(client, issued, quote):
    rfq = issued(vendors=("v-a",))
    quote(VA, rfq)
    assert client.post(f"{RFQ}/invited/{rfq['id']}/decline", headers=VA).status_code == 409


def test_a_vendor_after_the_deadline_sees_the_rfq_but_cannot_quote(client, issued, clock):
    rfq = issued(vendors=("v-a",))
    clock.advance(days=3)
    d = client.get(f"{RFQ}/invited/{rfq['id']}", headers=VA).json()
    assert d["deadline_passed"] is True and d["can_quote"] is False and "deadline has passed" in d["blocked_reason"]
    assert client.post(f"{RFQ}/invited/{rfq['id']}/decline", headers=VA).status_code == 409


def test_a_vendor_user_without_a_company_profile_is_told_to_register(client, issued):
    issued()
    r = client.get(f"{RFQ}/invited", headers=VNONE)
    assert r.status_code == 403 and "Register your vendor profile" in r.json()["detail"]


def test_an_unverified_vendor_sees_invitations_but_cannot_quote(client, issued, world):
    rfq = issued(vendors=("v-a",))
    world.add_vendor("v-a", "u-va", "Acme Supplies", "suspended")
    d = client.get(f"{RFQ}/invited/{rfq['id']}", headers=VA).json()
    assert d["can_quote"] is False and "not verified" in d["blocked_reason"]
    assert client.get(f"{RFQ}/invited", headers=VX).status_code == 200


def test_the_vendor_service_being_down_gives_503_for_vendor_screens(client, issued, world):
    issued()
    world.vendor_down = True
    assert client.get(f"{RFQ}/invited", headers=VA).status_code == 503
    assert client.get(f"{QUO}/mine", headers=VA).status_code == 503


def test_dates_are_sent_with_a_utc_marker(client, issued, clock):
    rfq = issued(vendors=("v-a",))
    d = client.get(f"{RFQ}/invited/{rfq['id']}", headers=VA).json()["deadline"]
    assert d.endswith("Z") and d == (clock.now + timedelta(hours=48)).isoformat() + "Z"
    assert headers("vendor", "u-va")  # the helper itself keeps working
