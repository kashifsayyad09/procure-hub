import json

from app.models import VendorEvent
from tests.conftest import ADMIN, PROC, PROC2, URL, VENDOR_A, VENDOR_B, payload


def _review(client, vid, verb, h, version, **body):
    return client.post(f"{URL}/{vid}/{verb}", headers=h, json={"version": version, **body})


def test_submitting_an_incomplete_profile_lists_what_is_missing(client):
    v = client.post(URL, headers=VENDOR_A, json={"legal_name": "Tiny Traders"}).json()
    r = client.post(f"{URL}/{v['id']}/submit", headers=VENDOR_A)
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert "Missing: Tax ID." in detail and "Missing: At least one category." in detail and "Missing: A contact person with an email address." in detail
    assert client.get(f"{URL}/{v['id']}", headers=VENDOR_A).json()["status"] == "draft"


def test_submit_moves_a_complete_draft_to_pending(client, register):
    v = register()
    r = client.post(f"{URL}/{v['id']}/submit", headers=VENDOR_A)
    assert r.status_code == 200
    b = r.json()
    assert b["status"] == "pending" and b["submitted_at"] and b["version"] == v["version"] + 1
    assert [h["action"] for h in b["history"]] == ["created", "submitted"]
    assert client.post(f"{URL}/{v['id']}/submit", headers=VENDOR_A).status_code == 409  # already pending


def test_procurement_verifies_a_pending_vendor(client, pending):
    v = pending()
    r = _review(client, v["id"], "verify", PROC, v["version"], note="Documents checked")
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["status"] == "verified" and b["verified_by_name"] == "Pat Procurement" and b["verified_at"]
    assert b["history"][-1]["action"] == "verified" and b["history"][-1]["note"] == "Documents checked"
    assert client.get(f"{URL}/me", headers=VENDOR_A).json()["status"] == "verified"


def test_an_administrator_can_verify_too(client, pending):
    v = pending()
    assert _review(client, v["id"], "verify", ADMIN, v["version"]).json()["status"] == "verified"


def test_only_a_pending_vendor_can_be_verified_or_rejected(client, register, pending):
    draft = register()
    assert _review(client, draft["id"], "verify", PROC, draft["version"]).status_code == 409
    assert _review(client, draft["id"], "reject", PROC, draft["version"], reason="no").status_code in (409, 422)
    v = client.post(f"{URL}/{draft['id']}/submit", headers=VENDOR_A).json()
    done = _review(client, v["id"], "verify", PROC, v["version"]).json()
    assert _review(client, v["id"], "verify", PROC2, done["version"]).status_code == 409  # cannot verify twice
    assert _review(client, v["id"], "reject", PROC2, done["version"], reason="Changed my mind").status_code == 409


def test_a_reviewer_cannot_decide_on_a_profile_they_submitted(client, onboard):
    v = onboard(PROC)
    sub = client.post(f"{URL}/{v['id']}/submit", headers=PROC).json()
    assert sub["actions"] == ["edit"] and "Another reviewer" in sub["blocked_reason"]
    own = _review(client, v["id"], "verify", PROC, sub["version"])
    assert own.status_code == 403
    assert _review(client, v["id"], "reject", PROC, sub["version"], reason="Not good enough").status_code == 403
    assert client.get(f"{URL}/{v['id']}", headers=PROC).json()["status"] == "pending"
    other = client.get(f"{URL}/{v['id']}", headers=ADMIN).json()
    assert other["actions"] == ["edit", "verify", "reject"] and other["blocked_reason"] is None
    assert _review(client, v["id"], "verify", ADMIN, sub["version"]).json()["status"] == "verified"


def test_a_profile_changed_after_the_reviewer_opened_it_must_be_reviewed_again(client, pending):
    v = pending()
    seen = v["version"]
    client.put(f"{URL}/{v['id']}", headers=VENDOR_A, json=payload(tax_id="SNEAKYTAX1") | {"version": seen})  # vendor edits while pending
    r = _review(client, v["id"], "verify", PROC, seen)
    assert r.status_code == 409 and "changed somewhere else" in r.json()["detail"]
    fresh = client.get(f"{URL}/{v['id']}", headers=PROC).json()
    assert _review(client, v["id"], "verify", PROC, fresh["version"]).status_code == 200


def test_rejection_needs_a_reason_and_the_vendor_sees_it(client, pending):
    v = pending()
    assert _review(client, v["id"], "reject", PROC, v["version"]).status_code == 422
    assert _review(client, v["id"], "reject", PROC, v["version"], reason="  ").status_code == 422
    r = _review(client, v["id"], "reject", PROC, v["version"], reason="Tax ID does not match the registration.")
    assert r.status_code == 200
    mine = client.get(f"{URL}/me", headers=VENDOR_A).json()
    assert mine["status"] == "rejected" and mine["status_note"] == "Tax ID does not match the registration."
    assert mine["actions"] == ["edit", "submit"]


def test_a_rejected_vendor_can_fix_and_resubmit(client, pending):
    v = pending()
    rej = _review(client, v["id"], "reject", PROC, v["version"], reason="Wrong tax ID").json()
    fixed = client.put(f"{URL}/{v['id']}", headers=VENDOR_A, json=payload(tax_id="RIGHTTAX123") | {"version": rej["version"]})
    assert fixed.status_code == 200 and fixed.json()["status"] == "rejected"
    again = client.post(f"{URL}/{v['id']}/submit", headers=VENDOR_A).json()
    assert again["status"] == "pending" and again["status_note"] is None
    assert _review(client, v["id"], "verify", PROC2, again["version"]).json()["status"] == "verified"
    assert [h["action"] for h in client.get(f"{URL}/{v['id']}", headers=PROC).json()["history"]] == ["created", "submitted", "rejected", "updated", "submitted", "verified"]


def test_suspend_and_reinstate(client, pending):
    v = pending()
    ver = _review(client, v["id"], "verify", PROC, v["version"]).json()
    assert _review(client, v["id"], "suspend", PROC, ver["version"]).status_code == 422  # reason required
    sus = _review(client, v["id"], "suspend", ADMIN, ver["version"], reason="Failed quality audit").json()
    assert sus["status"] == "suspended" and sus["status_note"] == "Failed quality audit"
    assert client.get(f"{URL}/me", headers=VENDOR_A).json()["actions"] == []  # the vendor cannot edit or submit
    back = _review(client, v["id"], "reinstate", PROC, sus["version"], note="Audit passed")
    assert back.status_code == 200 and back.json()["status"] == "verified" and back.json()["status_note"] is None
    assert _review(client, v["id"], "reinstate", PROC, back.json()["version"]).status_code == 409  # not suspended any more


def test_only_a_verified_vendor_can_be_suspended(client, register, pending):
    d = register()
    assert _review(client, d["id"], "suspend", PROC, d["version"], reason="Because").status_code == 409
    p = client.post(f"{URL}/{d['id']}/submit", headers=VENDOR_A).json()
    assert _review(client, p["id"], "suspend", PROC, p["version"], reason="Because").status_code == 409


def test_a_suspended_vendor_cannot_edit_but_staff_can(client, pending):
    v = pending()
    ver = _review(client, v["id"], "verify", PROC, v["version"]).json()
    sus = _review(client, v["id"], "suspend", PROC, ver["version"], reason="Under review").json()
    assert client.put(f"{URL}/{v['id']}", headers=VENDOR_A, json=payload(city="Z") | {"version": sus["version"]}).status_code == 409
    assert client.put(f"{URL}/{v['id']}", headers=PROC, json=payload(city="Z") | {"version": sus["version"]}).status_code == 200
    assert client.post(f"{URL}/{v['id']}/submit", headers=VENDOR_A).status_code == 409


def test_changing_identity_details_of_a_verified_vendor_needs_verification_again(client, pending):
    v = pending()
    ver = _review(client, v["id"], "verify", PROC, v["version"]).json()
    r = client.put(f"{URL}/{v['id']}", headers=VENDOR_A, json=payload(legal_name="Acme Holdings Ltd", tax_id="NEWTAXID001") | {"version": ver["version"]})
    b = r.json()
    assert b["status"] == "pending" and b["verified_at"] is None and b["verified_by_name"] is None
    last = b["history"][-1]
    assert last["action"] == "reverification_required" and "company name" in last["note"] and "tax ID" in last["note"]
    assert _review(client, v["id"], "verify", PROC2, b["version"]).json()["status"] == "verified"


def test_changing_other_details_of_a_verified_vendor_keeps_it_verified(client, pending):
    v = pending()
    ver = _review(client, v["id"], "verify", PROC, v["version"]).json()
    r = client.put(f"{URL}/{v['id']}", headers=VENDOR_A, json=payload(city="Mysuru", payment_terms_days=60, categories=["software"]) | {"version": ver["version"]})
    assert r.json()["status"] == "verified" and r.json()["verified_by_name"] == "Pat Procurement"


def test_the_person_who_changes_a_verified_vendor_cannot_re_verify_it(client, pending):
    v = pending()
    ver = _review(client, v["id"], "verify", PROC, v["version"]).json()
    changed = client.put(f"{URL}/{v['id']}", headers=PROC, json=payload(tax_id="CHANGEDBYPAT1") | {"version": ver["version"]}).json()
    assert changed["status"] == "pending"
    assert _review(client, v["id"], "verify", PROC, changed["version"]).status_code == 403
    assert _review(client, v["id"], "verify", ADMIN, changed["version"]).status_code == 200


def test_actions_offered_match_the_caller_and_the_state(client, register, pending):
    d = register()
    assert client.get(f"{URL}/{d['id']}", headers=VENDOR_A).json()["actions"] == ["edit", "submit"]
    assert client.get(f"{URL}/{d['id']}", headers=PROC).json()["actions"] == ["edit", "submit"]
    p = client.post(f"{URL}/{d['id']}/submit", headers=VENDOR_A).json()
    assert p["actions"] == ["edit"]  # a pending profile can still be corrected, but not resubmitted
    assert client.get(f"{URL}/{d['id']}", headers=PROC).json()["actions"] == ["edit", "verify", "reject"]
    ver = _review(client, d["id"], "verify", PROC, p["version"]).json()
    assert client.get(f"{URL}/{d['id']}", headers=PROC2).json()["actions"] == ["edit", "suspend"]
    assert ver["actions"] == ["edit", "suspend"]
    assert client.get(f"{URL}/{d['id']}", headers=VENDOR_A).json()["actions"] == ["edit"]


def test_every_decision_writes_an_outbox_event(client, db, pending):
    v = pending()
    ver = _review(client, v["id"], "verify", PROC, v["version"]).json()
    sus = _review(client, v["id"], "suspend", PROC, ver["version"], reason="Audit").json()
    _review(client, v["id"], "reinstate", PROC, sus["version"])
    types = [e.type for e in db.query(VendorEvent).order_by(VendorEvent.created_at, VendorEvent.type)]
    assert sorted(types) == sorted(["vendor_registered", "vendor_submitted", "vendor_verified", "vendor_suspended", "vendor_reinstated"])
    suspended = next(e for e in db.query(VendorEvent) if e.type == "vendor_suspended")
    assert json.loads(suspended.payload)["reason"] == "Audit"


def test_a_vendor_cannot_use_review_endpoints_on_their_own_record(client, pending):
    v = pending()
    for verb, body in (("verify", {}), ("reject", {"reason": "abc"}), ("suspend", {"reason": "abc"}), ("reinstate", {})):
        assert _review(client, v["id"], verb, VENDOR_A, v["version"], **body).status_code == 403, verb
    assert client.get(f"{URL}/me", headers=VENDOR_A).json()["status"] == "pending"


def test_another_vendor_cannot_review_either(client, pending):
    v = pending()
    assert _review(client, v["id"], "verify", VENDOR_B, v["version"]).status_code == 403
